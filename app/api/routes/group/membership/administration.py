from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from typing import Optional
import uuid
import time

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.finance import MemberObligation
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from app.services.websocket_manager import ws_manager
from app.core.firebase_config import send_push_notification

router = APIRouter(prefix="/api/v1/groups", tags=["Group Member Administration"])

VALID_ROLES = {"MEMBER", "TREASURER", "ADMIN", "MODERATOR"}

class ChangeRoleRequest(BaseModel):
    role: str = Field(..., description="Target role: MEMBER, TREASURER, ADMIN, MODERATOR")
    title: Optional[str] = Field(default=None, description="Custom display badge/title (e.g., 'Treasurer', 'Elder', 'Auditor')")

class KickMemberRequest(BaseModel):
    reason: Optional[str] = Field(default="Removed by group administration", description="Explanation for audit log")
    ban: bool = Field(default=False, description="If true, marks status as BANNED preventing re-joining via invite link")

class TransferOwnershipRequest(BaseModel):
    new_owner_user_id: str = Field(..., description="UUID of the active member who will become the new group owner/creator")

def _verify_admin(session: Session, group_id: str, user_id: uuid.UUID) -> tuple[Group, GroupMembership]:
    """Helper verifying caller is an ADMIN of the group."""
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    caller_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user_id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()

    if not caller_membership or caller_membership.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required. Only group Admins can perform member moderation."
        )

    return group, caller_membership

@router.patch("/{group_id}/members/{target_user_id}/role", summary="Admin: Promote or Demote Member Role")
def change_member_role(
    group_id: str,
    target_user_id: str,
    payload: ChangeRoleRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Allows a Group Admin to promote or demote a member (e.g. appointing a TREASURER or co-ADMIN).
    - Validates target roles
    - Prevents admins from demoting the primary group creator
    - Broadcasts real-time role change notice to group chat
    """
    target_role = payload.role.upper().strip()
    if target_role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{payload.role}'. Allowed roles: {', '.join(sorted(VALID_ROLES))}"
        )

    try:
        target_uuid = uuid.UUID(target_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user UUID format.")

    group, caller_membership = _verify_admin(session, group_id, current_user.id)

    target_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == target_uuid,
            GroupMembership.status == "ACTIVE"
        )
    ).first()

    if not target_membership:
        raise HTTPException(status_code=404, detail="Target member not found in this group.")

    # Prevent demoting the primary creator unless ownership was transferred
    if target_uuid == group.created_by_user_id and target_role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot demote the primary group creator. Group ownership must be transferred first."
        )

    old_role = target_membership.role
    target_membership.role = target_role
    if payload.title is not None:
        target_membership.title = payload.title.strip() or None

    session.add(target_membership)
    session.commit()
    session.refresh(target_membership)

    # Post system notification to chat
    target_user = session.get(User, target_uuid)
    target_name = target_user.full_name if target_user else "A member"
    
    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"{current_user.full_name} updated {target_name}'s role to {target_role}.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    # Push: direct notification to the member whose role changed
    if target_user and target_user.fcm_token:
        send_push_notification(
            token=target_user.fcm_token,
            title="Your Role Was Updated",
            body=f"You are now a {target_role} in '{group.name}'.",
            data={"type": "ROLE_CHANGED", "group_id": group_id, "new_role": target_role}
        )

    return {
        "status": "success",
        "message": f"Member role updated from {old_role} to {target_role}.",
        "data": {
            "group_id": group_id,
            "user_id": str(target_uuid),
            "role": target_membership.role,
            "title": target_membership.title
        }
    }

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

    group, caller_membership = _verify_admin(session, group_id, current_user.id)

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

@router.post("/{group_id}/transfer-ownership", summary="Owner: Transfer Group Ownership")
def transfer_group_ownership(
    group_id: str,
    payload: TransferOwnershipRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Transfers primary group creator ownership to another active member.
    - Only the CURRENT CREATOR (`created_by_user_id`) can invoke this
    - Automatically elevates the new owner to `ADMIN`
    - Preserves previous owner as an active `ADMIN`
    - Broadcasts system milestone message in group chat
    """
    try:
        new_owner_uuid = uuid.UUID(payload.new_owner_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid new owner user UUID format.")

    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    if group.created_by_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the primary group owner can transfer ownership of this group."
        )

    if new_owner_uuid == current_user.id:
        raise HTTPException(status_code=400, detail="You are already the owner of this group.")

    # Verify the new owner is an active member
    new_owner_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == new_owner_uuid,
            GroupMembership.status == "ACTIVE"
        )
    ).first()

    if not new_owner_membership:
        raise HTTPException(status_code=400, detail="New owner must be an active member of the group.")

    # 1. Update Group creator
    group.created_by_user_id = new_owner_uuid
    group.updated_at = int(time.time() * 1000)
    session.add(group)

    # 2. Promote new owner to ADMIN
    new_owner_membership.role = "ADMIN"
    new_owner_membership.title = "Owner"
    session.add(new_owner_membership)

    session.commit()

    new_owner_user = session.get(User, new_owner_uuid)
    new_owner_name = new_owner_user.full_name if new_owner_user else "Member"

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"Group ownership transferred from {current_user.full_name} to {new_owner_name}.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    # Push: direct notification to the new owner
    if new_owner_user and new_owner_user.fcm_token:
        send_push_notification(
            token=new_owner_user.fcm_token,
            title="You're Now the Group Owner 👑",
            body=f"{current_user.full_name} transferred ownership of '{group.name}' to you.",
            data={"type": "OWNERSHIP_TRANSFERRED", "group_id": group_id}
        )

    return {
        "status": "success",
        "message": f"Group ownership successfully transferred to {new_owner_name}.",
        "data": {
            "group_id": group_id,
            "new_owner_user_id": str(new_owner_uuid),
            "previous_owner_user_id": str(current_user.id)
        }
    }
