import uuid
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from app.core.firebase_config import send_push_notification
from .schemas import ChangeRoleRequest
from .helpers import verify_admin, VALID_ROLES

router = APIRouter()

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

    group, caller_membership = verify_admin(session, group_id, current_user.id)

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
