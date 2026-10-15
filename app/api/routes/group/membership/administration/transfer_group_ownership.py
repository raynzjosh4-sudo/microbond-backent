import uuid
import time
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from app.core.firebase_config import send_push_notification
from .schemas import TransferOwnershipRequest

router = APIRouter()

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
