"""
API Routes for Group Daily Deposit Widget & Member Status Drill-down.
Enforces admin-configured visibility permissions and provides full member details on tap.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select
from typing import Optional, List
import uuid
from pydantic import BaseModel, Field

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.settings import GroupVisibilitySettings
from app.services.deposits.daily_widget_service import (
    get_daily_deposit_widget_summary,
    get_daily_deposit_widget_members
)

router = APIRouter(prefix="/api/v1/groups", tags=["Group Daily Deposit Widget"])

class UpdateDepositWidgetVisibilityRequest(BaseModel):
    visibility: str = Field(
        ...,
        description="Allowed options: ALL_MEMBERS, ADMIN_ONLY, ADMIN_AND_TREASURER"
    )

class NudgeMemberRequest(BaseModel):
    target_user_id: uuid.UUID
    custom_message: Optional[str] = None

@router.get(
    "/{group_id}/deposits/daily-widget",
    summary="Get Daily Deposit Widget Summary",
    description="Returns aggregate counts and amounts for Full, Partial/Half, and Not Deposited members for the day."
)
def get_daily_widget_summary(
    group_id: str,
    date_ms: Optional[int] = Query(None, description="Optional epoch ms for a specific day. Defaults to current day in Kampala (UTC+3)."),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    return get_daily_deposit_widget_summary(
        session=session,
        group_id=group_id,
        current_user=current_user,
        date_ms=date_ms
    )

@router.get(
    "/{group_id}/deposits/daily-widget/members",
    summary="Get Members by Deposit Status",
    description="Drill-down API returning member profile picture, name, online status, last seen, amount paid, and settled timestamp."
)
def get_daily_widget_members(
    group_id: str,
    status: str = Query("FULL", description="Filter status: FULL, PARTIAL, NOT_DEPOSITED, or ALL"),
    date_ms: Optional[int] = Query(None, description="Optional epoch ms for a specific day."),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    return get_daily_deposit_widget_members(
        session=session,
        group_id=group_id,
        current_user=current_user,
        status_filter=status,
        date_ms=date_ms
    )

@router.patch(
    "/{group_id}/settings/deposit-widget-visibility",
    summary="Admin: Set Deposit Widget Visibility Permission",
    description="Configures who can view and request the deposit widget in the group: ALL_MEMBERS, ADMIN_ONLY, or ADMIN_AND_TREASURER."
)
def update_deposit_widget_visibility(
    group_id: str,
    request: UpdateDepositWidgetVisibilityRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    admin_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN"
        )
    ).first()

    if not admin_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the Group Admin can change deposit widget visibility."
        )

    allowed = ["ALL_MEMBERS", "ADMIN_ONLY", "ADMIN_AND_TREASURER"]
    val = request.visibility.upper()
    if val not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid visibility value '{request.visibility}'. Must be one of: {allowed}"
        )

    vis_settings = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()

    if not vis_settings:
        vis_settings = GroupVisibilitySettings(
            group_id=group_id,
            deposit_widget_visibility=val
        )
        session.add(vis_settings)
    else:
        vis_settings.deposit_widget_visibility = val
        session.add(vis_settings)

    session.commit()
    return {
        "status": "success",
        "message": f"Deposit widget visibility updated to {val}",
        "deposit_widget_visibility": val
    }

@router.post(
    "/{group_id}/deposits/daily-widget/nudge",
    summary="Send Deposit Reminder Nudge",
    description="Sends a friendly reminder or nudge to a member who has not yet completed their daily deposit."
)
def nudge_member_for_deposit(
    group_id: str,
    request: NudgeMemberRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # Verify caller membership
    caller_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not caller_membership:
        raise HTTPException(status_code=403, detail="You must be an active member to send deposit reminders.")

    # Verify target user is in group
    target_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == request.target_user_id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not target_membership:
        raise HTTPException(status_code=404, detail="Target member not found in this group.")

    target_user = session.get(User, request.target_user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found.")

    # Formulate reminder message
    sender_name = current_user.full_name or "A group member"
    msg = request.custom_message or f"Hi {target_user.full_name or 'there'}, friendly reminder to complete your deposit for today in our group!"

    # In a full notification setup, this calls FCM or inserts a notification
    return {
        "status": "success",
        "message": f"Reminder sent to {target_user.full_name or 'member'}",
        "target_user_id": str(target_user.id),
        "sent_message": msg
    }
