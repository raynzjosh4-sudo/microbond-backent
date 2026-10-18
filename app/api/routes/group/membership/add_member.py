from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select
from typing import Optional
from pydantic import BaseModel, Field
import uuid
import time
import logging

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.api.routes.group.chat.messages import broadcast_system_message_sync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/groups", tags=["Group Membership"])

class AdminAddMemberRequest(BaseModel):
    user_id: str = Field(..., description="The unique UUID of the user to be added to the group.")
    role: Optional[str] = Field(default="MEMBER", description="The role to assign to the user (e.g., MEMBER, ADMIN).")

class AdminAddMemberResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None

@router.post("/{group_id}/members/add", response_model=AdminAddMemberResponse, summary="Admin: Add a User to the Group Directly")
def admin_add_member(
    group_id: str,
    request: AdminAddMemberRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Directly adds a user to a group without requiring them to accept an invite.
    Only users with the 'ADMIN' role in the specified group can perform this action.
    """
    # 1. Authorize: Check if current user is an admin of the group
    admin_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN"
        )
    ).first()

    if not admin_membership:
        logger.warning(f"Unauthorized add member attempt by user {current_user.id} in group {group_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Only a Group Admin can add members directly."
        )

    # 2. Validate: Check if group exists
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")
        
    # 3. Validate: Check if target user exists and parse UUID
    try:
        target_user_uuid = uuid.UUID(request.user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format. Must be a valid UUID.")

    target_user = session.exec(select(User).where(User.id == target_user_uuid)).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User to add not found in the system.")

    # 3b. Privacy Enforcement: Check who can add this user to groups
    from app.services.privacy import can_add_to_group
    allowed, rejection_reason = can_add_to_group(target_user, current_user, session)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=rejection_reason or "This user's privacy settings prevent them from being added to groups.",
        )

    # 4. Process: Check if user is already a member
    existing_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == target_user.id
        )
    ).first()

    if existing_membership:
        if existing_membership.status == "ACTIVE":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already an active member of this group.")
        else:
            # Re-activate them if they had previously left
            existing_membership.status = "ACTIVE"
            existing_membership.role = request.role.upper() if request.role else "MEMBER"
            existing_membership.joined_at = int(time.time() * 1000)
            existing_membership.left_at = None
            existing_membership.invited_by_user_id = current_user.id
            
            # Update group member count
            group.member_count += 1
            
            session.add(existing_membership)
            session.add(group)
            try:
                session.commit()
                session.refresh(existing_membership)
                
                # Chat integration
                broadcast_system_message_sync(
                    group_id=group_id,
                    message_text=f"{current_user.full_name} re-added {target_user.full_name or 'a user'} to the group.",
                    message_type="SYSTEM_EVENT",
                    sender_id=str(current_user.id),
                    session=session,
                    background_tasks=background_tasks
                )
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to reactivate membership for user {target_user.id} in group {group_id}: {e}")
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to add user to the group.")

            return {
                "status": "success", 
                "message": "User re-added to the group successfully.",
                "data": {
                    "membership_id": existing_membership.membership_id,
                    "user_id": str(existing_membership.user_id),
                    "role": existing_membership.role,
                    "joined_at": existing_membership.joined_at
                }
            }

    # 5. Process: Verify capacity limits
    if group.max_members and group.member_count >= group.max_members:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Group has reached its maximum member capacity.")

    # 6. Process: Create new membership
    new_membership = GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=group_id,
        user_id=target_user.id,
        role=request.role.upper() if request.role else "MEMBER",
        status="ACTIVE",
        invited_by_user_id=current_user.id,
        joined_at=int(time.time() * 1000)
    )

    group.member_count += 1

    session.add(new_membership)
    session.add(group)
    
    try:
        session.commit()
        session.refresh(new_membership)
        
        # Chat integration
        broadcast_system_message_sync(
            group_id=group_id,
            message_text=f"{current_user.full_name} added {target_user.full_name or 'a new user'} to the group.",
            message_type="SYSTEM_EVENT",
            sender_id=str(current_user.id),
            session=session,
            background_tasks=background_tasks
        )
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to create membership for user {target_user.id} in group {group_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to add user to the group due to an internal error.")

    return {
        "status": "success", 
        "message": "User added to the group successfully.",
        "data": {
            "membership_id": new_membership.membership_id,
            "user_id": str(new_membership.user_id),
            "role": new_membership.role,
            "joined_at": new_membership.joined_at
        }
    }
