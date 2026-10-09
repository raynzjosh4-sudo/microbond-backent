from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
from sqlmodel import Session

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership

router = APIRouter(prefix="/api/v1/groups", tags=["Group Membership"])

class UpdateMembershipRequest(BaseModel):
    is_chat_locked: Optional[bool] = Field(default=None, description="Require biometric/device lock to open this chat")
    mute_notifications: Optional[bool] = Field(default=None, description="Mute push notifications for this group")
    custom_notification_tone: Optional[str] = Field(default=None, description="Filename or name of the custom tone")
    show_previews: Optional[bool] = Field(default=None, description="Show message previews in the notification/list")
    is_favorite: Optional[bool] = Field(default=None, description="Pin this group to the top of the list")
    auto_pay_my_turn: Optional[bool] = Field(default=None, description="Automatically trigger payment logic when my turn comes")
    auto_approve_small_requests: Optional[bool] = Field(default=None, description="Automatically approve payout requests below a certain amount")
    auto_approve_max_amount: Optional[float] = Field(default=None, description="The maximum amount to auto-approve")

@router.patch("/{group_id}/membership/me", summary="Update Personal Membership Settings")
def update_my_membership_settings(
    group_id: str,
    request: UpdateMembershipRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # 1. Fetch the user's membership in this group
    membership = session.query(GroupMembership).filter(
        GroupMembership.group_id == group_id,
        GroupMembership.user_id == current_user.id
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not a member of this group or the group does not exist."
        )

    # 2. Apply updates selectively
    if request.is_chat_locked is not None:
        membership.is_chat_locked = request.is_chat_locked
        
    if request.mute_notifications is not None:
        membership.mute_notifications = request.mute_notifications
        
    if request.custom_notification_tone is not None:
        membership.custom_notification_tone = request.custom_notification_tone
        
    if request.show_previews is not None:
        membership.show_previews = request.show_previews
        
    if request.is_favorite is not None:
        membership.is_favorite = request.is_favorite
        
    if request.auto_pay_my_turn is not None:
        membership.auto_pay_my_turn = request.auto_pay_my_turn
        
    if request.auto_approve_small_requests is not None:
        if request.auto_approve_small_requests == True and request.auto_approve_max_amount is None and membership.auto_approve_max_amount is None:
            raise HTTPException(status_code=400, detail="You must specify a maximum amount when enabling auto-approve.")
        membership.auto_approve_small_requests = request.auto_approve_small_requests
        
    if request.auto_approve_max_amount is not None:
        if request.auto_approve_max_amount < 0:
            raise HTTPException(status_code=400, detail="Auto-approve maximum amount cannot be negative.")
        membership.auto_approve_max_amount = request.auto_approve_max_amount

    # 3. Save to database
    session.commit()
    session.refresh(membership)

    return {
        "status": "success",
        "message": "Membership settings updated.",
        "data": {
            "is_chat_locked": membership.is_chat_locked,
            "mute_notifications": membership.mute_notifications,
            "custom_notification_tone": membership.custom_notification_tone,
            "show_previews": membership.show_previews,
            "is_favorite": membership.is_favorite,
            "auto_pay_my_turn": membership.auto_pay_my_turn,
            "auto_approve_small_requests": membership.auto_approve_small_requests,
            "auto_approve_max_amount": membership.auto_approve_max_amount
        }
    }
