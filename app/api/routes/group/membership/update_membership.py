from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.finance import MemberObligation
from app.models.group.settings import GroupVisibilitySettings
from app.models.user.userpaymentmethod.payment_method import UserPaymentMethod

router = APIRouter(prefix="/api/v1/groups", tags=["Group Membership"])

class UpdateMembershipRequest(BaseModel):
    is_chat_locked: Optional[bool] = Field(default=None, description="Require biometric/device lock to open this chat")
    mute_notifications: Optional[bool] = Field(default=None, description="Mute push notifications for this group")
    custom_notification_tone: Optional[str] = Field(default=None, description="Filename or name of the custom tone")
    show_previews: Optional[bool] = Field(default=None, description="Show message previews in the notification/list")
    include_chat_in_export: Optional[bool] = Field(default=None, description="Include chat history in records export")
    is_favorite: Optional[bool] = Field(default=None, description="Pin this group to the top of the list")
    auto_pay_my_turn: Optional[bool] = Field(default=None, description="Automatically trigger payment logic when my turn comes")
    auto_approve_small_requests: Optional[bool] = Field(default=None, description="Automatically approve payout requests below a certain amount")
    auto_approve_max_amount: Optional[float] = Field(
        default=None,
        ge=0,
        le=500000,
        description="The maximum amount to auto-approve (must not exceed 500,000 UGX)"
    )


def _mask_account(number: Optional[str]) -> str:
    if not number:
        return "****"
    cleaned = str(number).strip()
    if len(cleaned) < 4:
        return "****"
    return f"**** {cleaned[-4:]}"


def _format_group_type_label(group_type: str) -> str:
    mapping = {
        "GOAL_SAVINGS": "Goal Savings",
        "MERRY_GO_ROUND": "Merry-Go-Round",
        "INVESTMENT_CLUB": "Investment Club",
        "WELFARE_FUND": "Welfare Fund",
        "SHARED_WALLET": "Shared Wallet",
        "EVENT_COMMITTEE": "Event Committee",
        "FUNDRAISER": "Fundraiser Campaign",
        "BILL_SPLIT": "Bill Split",
        "ASSOCIATION_DUES": "Association Dues",
        "STANDARD": "Standard Savings"
    }
    return mapping.get(group_type, group_type.replace("_", " ").title())


@router.get("/{group_id}/membership/me", summary="Get Personal Membership Settings & Status")
def get_my_membership_settings(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the personal membership settings, standing, and summary for the current user in this group.
    Powers the 'Your settings' screen in the Android app.
    """
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not a member of this group."
        )

    # 1. Fetch active payment method
    pm = None
    if membership.payment_method_id:
        pm = session.exec(
            select(UserPaymentMethod).where(
                UserPaymentMethod.id == membership.payment_method_id,
                UserPaymentMethod.user_id == current_user.id
            )
        ).first()

    if not pm:
        pm = session.exec(
            select(UserPaymentMethod).where(
                UserPaymentMethod.user_id == current_user.id,
                UserPaymentMethod.is_default == True
            )
        ).first()

    payment_method_info = {
        "payment_method_id": pm.id if pm else None,
        "provider_name": pm.provider_name if pm else "MTN Mobile Money",
        "masked_number": _mask_account(pm.account_number if pm else current_user.phone_number),
        "account_type": pm.account_type if pm else "MOBILE_MONEY",
        "is_verified": pm.is_verified if pm else True,
        "is_fallback": pm is None
    }

    # 2. Check if user can exit group
    pending_debt = session.exec(
        select(MemberObligation).where(
            MemberObligation.group_id == group_id,
            MemberObligation.user_id == current_user.id,
            MemberObligation.status.in_(["PENDING", "LATE", "OVERDUE", "DEFAULTED"])
        )
    ).first() is not None

    is_creator_with_members = (group.created_by_user_id == current_user.id and group.member_count > 1)
    can_leave = not pending_debt and not is_creator_with_members
    leave_restriction_reason = None
    if pending_debt:
        leave_restriction_reason = "You have unsettled financial obligations in this group."
    elif is_creator_with_members:
        leave_restriction_reason = "You are the creator of this group. You must transfer ownership to another admin before leaving."

    # 3. Format visibility/subtitle
    visibility_label = "private to you" if group.member_count <= 1 else f"{group.member_count} members · {group.visibility.lower()}"

    # 4. Check if admin allows members to see their savings totals
    vis_settings = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()
    is_admin = (membership.role == "ADMIN")
    show_savings = is_admin or getattr(vis_settings, "vis_member_total_savings", True) if vis_settings else True

    return {
        "status": "success",
        "data": {
            "group_id": group.group_id,
            "group_name": group.name,
            "group_type": group.type,
            "group_type_label": _format_group_type_label(group.type),
            "member_count": group.member_count,
            "visibility": group.visibility,
            "visibility_label": visibility_label,
            "currency": group.currency,
            "role": membership.role,
            "status": membership.status,
            
            # Financial stat ("My total saved" / "My total contributed")
            # Hidden when admin disables vis_member_total_savings
            "total_saved": membership.total_contributed if show_savings else None,
            "total_saved_formatted": f"{group.currency} {membership.total_contributed:,}" if show_savings else "Hidden by admin",
            "total_contributed": membership.total_contributed if show_savings else None,
            "savings_hidden": not show_savings,
            
            # "My payment method"
            "payment_method": payment_method_info,
            
            # "Mute / custom notifications"
            "mute_notifications": membership.mute_notifications,
            "notifications_label": "On" if membership.mute_notifications else "Off",
            "custom_notification_tone": membership.custom_notification_tone or "Default (Chime)",
            "show_previews": membership.show_previews,
            
            # "Export my records"
            "include_chat_in_export": getattr(membership, "include_chat_in_export", False),
            
            # "Exit group"
            "can_leave": can_leave,
            "leave_restriction_reason": leave_restriction_reason,
            
            # Additional personal preferences
            "is_chat_locked": membership.is_chat_locked,
            "is_favorite": membership.is_favorite,
            "auto_pay_my_turn": membership.auto_pay_my_turn,
            "auto_approve_small_requests": membership.auto_approve_small_requests,
            "auto_approve_max_amount": membership.auto_approve_max_amount,
            "joined_at": membership.joined_at
        }
    }


@router.patch("/{group_id}/membership/me", summary="Update Personal Membership Settings")
def update_my_membership_settings(
    group_id: str,
    request: UpdateMembershipRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # 1. Fetch the user's membership in this group
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
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

    if request.include_chat_in_export is not None:
        membership.include_chat_in_export = request.include_chat_in_export
        
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
        if request.auto_approve_max_amount > 500000:
            raise HTTPException(status_code=400, detail="Auto-approve amount cannot exceed 500,000 UGX.")
        membership.auto_approve_max_amount = request.auto_approve_max_amount

    # 3. Save to database
    session.add(membership)
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
            "include_chat_in_export": membership.include_chat_in_export,
            "is_favorite": membership.is_favorite,
            "auto_pay_my_turn": membership.auto_pay_my_turn,
            "auto_approve_small_requests": membership.auto_approve_small_requests,
            "auto_approve_max_amount": membership.auto_approve_max_amount
        }
    }
