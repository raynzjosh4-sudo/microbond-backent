from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select
from typing import Literal, Optional
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
    user_id: Optional[str] = Field(default=None, description="The unique UUID of the user to invite.")
    phone_number: Optional[str] = Field(default=None, description="The verified phone number of the user to invite.")
    role: Optional[str] = Field(default="MEMBER", description="The role to assign to the user (e.g., MEMBER, ADMIN).")

class InvitationResponseRequest(BaseModel):
    action: Literal["ACCEPT", "REJECT"]

class AdminAddMemberResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None

@router.post("/{group_id}/members/add", response_model=AdminAddMemberResponse, summary="Admin: Invite a User to the Group")
def admin_add_member(
    group_id: str,
    request: AdminAddMemberRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Invite a user to join; the user must accept before becoming a member."""
    # 1. Authorize: Check if current user is an admin of the group
    admin_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN",
            GroupMembership.status == "ACTIVE",
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
        
    if bool(request.user_id) == bool(request.phone_number):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide exactly one of user_id or phone_number.",
        )

    if request.user_id:
        try:
            target_user_uuid = uuid.UUID(request.user_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format. Must be a valid UUID.")
        target_user = session.exec(select(User).where(User.id == target_user_uuid)).first()
    else:
        target_user = session.exec(select(User).where(User.phone_number == request.phone_number)).first()
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
        if existing_membership.status == "PENDING_ACCEPTANCE":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has a pending invitation.")
        if existing_membership.status not in {"LEFT", "DECLINED"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User cannot be invited in their current membership state.")

        existing_membership.status = "PENDING_ACCEPTANCE"
        existing_membership.role = request.role.upper() if request.role else "MEMBER"
        existing_membership.joined_at = int(time.time() * 1000)
        existing_membership.left_at = None
        existing_membership.invited_by_user_id = current_user.id
        session.add(existing_membership)
        try:
            session.commit()
            session.refresh(existing_membership)
        except Exception as e:
            session.rollback()
            logger.error(f"Failed to create invitation for user {target_user.id} in group {group_id}: {e}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to invite user to the group.")

        _notify_invited_user(target_user, group)
        return _invitation_response(existing_membership, target_user)

    # 5. Process: Verify capacity limits
    if group.max_members and group.member_count >= group.max_members:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Group has reached its maximum member capacity.")

    # 6. Process: Create a pending invitation; acceptance activates membership.
    new_membership = GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=group_id,
        user_id=target_user.id,
        role=request.role.upper() if request.role else "MEMBER",
        status="PENDING_ACCEPTANCE",
        invited_by_user_id=current_user.id,
        joined_at=int(time.time() * 1000)
    )

    session.add(new_membership)
    
    try:
        session.commit()
        session.refresh(new_membership)
        
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to create invitation for user {target_user.id} in group {group_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to invite user to the group.")

    _notify_invited_user(target_user, group)
    return _invitation_response(new_membership, target_user)


def _invitation_response(membership: GroupMembership, target_user: User) -> dict:
    return {
        "status": "success",
        "message": "Invitation sent. The user must accept before joining the group.",
        "data": {
            "membership_id": membership.membership_id,
            "user_id": str(target_user.id),
            "role": membership.role,
            "membership_status": membership.status,
            "invited_at": membership.joined_at,
        },
    }


def _notify_invited_user(target_user: User, group: Group) -> None:
    if not target_user.fcm_token:
        return
    try:
        from app.core.firebase_config import send_push_notification

        send_push_notification(
            token=target_user.fcm_token,
            title="Group invitation",
            body=f"{group.name}: review your invitation to join.",
            data={"type": "GROUP_INVITATION", "group_id": group.group_id},
        )
    except Exception as exc:
        logger.warning(f"Failed to notify invited user {target_user.id}: {exc}")


@router.get("/members/invitations/pending", summary="List My Pending Group Invitations")
def list_pending_invitations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    invitations = session.exec(
        select(GroupMembership, Group)
        .join(Group, Group.group_id == GroupMembership.group_id)
        .where(
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "PENDING_ACCEPTANCE",
        )
    ).all()
    return {
        "status": "success",
        "data": [
            {
                "group_id": group.group_id,
                "group_name": group.name,
                "group_type": group.type,
                "membership_id": membership.membership_id,
                "invited_by_user_id": str(membership.invited_by_user_id) if membership.invited_by_user_id else None,
                "invited_at": membership.joined_at,
            }
            for membership, group in invitations
        ],
    }


@router.post("/{group_id}/members/invitation/respond", summary="Accept or Reject a Group Invitation")
def respond_to_invitation(
    group_id: str,
    request: InvitationResponseRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "PENDING_ACCEPTANCE",
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending invitation found for this group.")

    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found.")

    if request.action == "REJECT":
        membership.status = "DECLINED"
        membership.left_at = int(time.time() * 1000)
        session.add(membership)
        session.commit()
        return {"status": "success", "message": "Invitation rejected.", "membership_status": membership.status}

    if group.max_members and group.member_count >= group.max_members:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Group has reached its maximum member capacity.")

    membership.status = "ACTIVE"
    membership.joined_at = int(time.time() * 1000)
    membership.left_at = None
    group.member_count += 1
    session.add(membership)
    session.add(group)
    session.commit()

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"{current_user.full_name or 'A new member'} accepted an invitation to join the group.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks,
    )

    if group.max_members and group.member_count >= group.max_members and group.type == "MERRY_GO_ROUND":
        from app.services.group.launcher_service import execute_group_launch

        try:
            execute_group_launch(session, group_id)
            session.commit()
        except Exception as launch_err:
            logger.warning(f"Auto-launch error after invitation acceptance for group {group_id}: {launch_err}")

    return {"status": "success", "message": "Invitation accepted.", "membership_status": membership.status}
