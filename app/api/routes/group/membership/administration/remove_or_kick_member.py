import uuid
import time
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.finance import MemberObligation
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from app.services.websocket_manager import ws_manager
from app.core.firebase_config import send_push_notification
from .schemas import KickMemberRequest
from .helpers import verify_admin

router = APIRouter()

@router.post("/{group_id}/members/{target_user_id}/remove", summary="Admin: Kick or Ban Member")
async def remove_or_kick_member(
    group_id: str,
    target_user_id: str,
    payload: KickMemberRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Allows a Group Admin to remove or ban a member from the group.
    - Prevents kicking the group creator
    - Checks for pending obligations/debts (flags warning in audit)
    - Automatically updates member count
    - Immediately disconnects the target's live WebSocket connection
    - Broadcasts system notice to group chat
    """
    try:
        target_uuid = uuid.UUID(target_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user UUID format.")

    if target_uuid == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot kick yourself. Use the leave group endpoint instead."
        )

    group, caller_membership = verify_admin(session, group_id, current_user.id)

    if target_uuid == group.created_by_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot kick the primary creator of this group."
        )

    target_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == target_uuid,
            GroupMembership.status == "ACTIVE"
        )
    ).first()

    if not target_membership:
        raise HTTPException(status_code=404, detail="Target member is not active in this group.")

    # Check if target has unpaid debts
    pending_debt = session.exec(
        select(MemberObligation).where(
            MemberObligation.group_id == group_id,
            MemberObligation.user_id == target_uuid,
            MemberObligation.status.in_(["PENDING", "LATE"])
        )
    ).first()

    target_user = session.get(User, target_uuid)
    target_name = target_user.full_name if target_user else "Member"

    # Action: BAN (mark as BANNED) or KICK (delete membership)
    now_ms = int(time.time() * 1000)
    if payload.ban:
        target_membership.status = "BANNED"
        target_membership.left_at = now_ms
        session.add(target_membership)
    else:
        session.delete(target_membership)

    group.member_count = max(0, group.member_count - 1)
    session.add(group)
    session.commit()

    # Disconnect live WebSocket for the kicked user
    await ws_manager.force_disconnect_user(str(target_uuid), reason="Removed from group by administrator")

    action_word = "banned from" if payload.ban else "removed from"
    debt_notice = " (Note: Member has unsettled payment obligations)" if pending_debt else ""

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"{target_name} was {action_word} the group by {current_user.full_name}. Reason: {payload.reason}{debt_notice}",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    # Push: direct notification to the kicked/banned member
    if target_user and target_user.fcm_token:
        send_push_notification(
            token=target_user.fcm_token,
            title="Removed from Group",
            body=f"You were {action_word} '{group.name}'. Reason: {payload.reason}",
            data={"type": "MEMBER_KICKED", "group_id": group_id, "action": "BANNED" if payload.ban else "REMOVED"}
        )

    return {
        "status": "success",
        "message": f"Member {target_name} successfully {action_word} the group.",
        "data": {
            "group_id": group_id,
            "target_user_id": str(target_uuid),
            "action": "BANNED" if payload.ban else "REMOVED",
            "had_outstanding_debt": bool(pending_debt is not None)
        }
    }
