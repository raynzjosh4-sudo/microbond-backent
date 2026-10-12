"""
Member SMS Notification Preferences (per-group)
------------------------------------------------
Members opt in/out of SMS reminders for a specific group here.
They also see the 50 UGX per-deposit fee disclosure before opting in.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupFinancialSettings
from app.communications.sms_service import (
    SMS_FEE_UGX,
    send_sms_opt_in_consent_notice
)

router = APIRouter(prefix="/api/v1/groups", tags=["Group Membership"])


class UpdateSmsPreferencesRequest(BaseModel):
    sms_reminders_opted_in: Optional[bool] = None
    sms_reminder_hours_before: Optional[int] = None  # e.g. 24, 48, 72
    email_reminders_opted_in: Optional[bool] = None
    email_reminder_hours_before: Optional[int] = None  # e.g. 24, 48, 72


class SmsPreferencesResponse(BaseModel):
    group_id: str
    sms_reminders_opted_in: bool
    sms_reminder_hours_before: int
    sms_fee_acknowledged: bool
    pending_sms_fee_ugx: int
    email_reminders_opted_in: bool
    email_reminder_hours_before: int
    group_sms_reminders_enabled: bool  # Whether admin has it turned on at all
    fee_notice: str


@router.get(
    "/{group_id}/members/me/sms-preferences",
    summary="Get my SMS & Email reminder preferences for this group",
    response_model=SmsPreferencesResponse
)
def get_my_sms_preferences(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()

    if not membership:
        raise HTTPException(status_code=403, detail="You are not a member of this group.")

    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    fin = session.exec(
        select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group_id)
    ).first()

    group_sms_enabled = fin.enable_sms_call_reminders if fin else False
    currency = group.currency if group else "UGX"

    return SmsPreferencesResponse(
        group_id=group_id,
        sms_reminders_opted_in=membership.sms_reminders_opted_in,
        sms_reminder_hours_before=membership.sms_reminder_hours_before,
        sms_fee_acknowledged=membership.sms_fee_acknowledged,
        pending_sms_fee_ugx=membership.pending_sms_fee_ugx,
        email_reminders_opted_in=membership.email_reminders_opted_in,
        email_reminder_hours_before=membership.email_reminder_hours_before,
        group_sms_reminders_enabled=group_sms_enabled,
        fee_notice=(
            f"Enabling SMS reminders will add a {currency} {SMS_FEE_UGX} fee to each deposit you make "
            f"into this group. This covers the cost of the SMS notification."
            if group_sms_enabled else
            "The group admin has not enabled SMS reminders for this group yet."
        )
    )


@router.patch(
    "/{group_id}/members/me/sms-preferences",
    summary="Update my SMS reminder preferences for this group"
)
def update_my_sms_preferences(
    group_id: str,
    request: UpdateSmsPreferencesRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Allows a member to:
    - Opt in/out of SMS reminders (sms_reminders_opted_in)
    - Set how many hours before their due date they want the reminder (sms_reminder_hours_before)

    First time they opt in:
    - They receive a one-time consent SMS explaining the 50 UGX per-deposit fee.
    - sms_fee_acknowledged is set to True.

    Constraints:
    - The group must have enable_sms_call_reminders = True (admin-controlled).
    - sms_reminder_hours_before must be between 1 and 168 (1 hour to 7 days).
    """
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()

    if not membership:
        raise HTTPException(status_code=403, detail="You are not a member of this group.")

    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    fin = session.exec(
        select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group_id)
    ).first()

    # Check opt-in request
    if request.sms_reminders_opted_in is True:
        if not fin or not fin.enable_sms_call_reminders:
            raise HTTPException(
                status_code=400,
                detail="The group admin has not enabled SMS reminders for this group. "
                       "Ask your group admin to enable it first."
            )
        first_time_opt_in = not membership.sms_reminders_opted_in
        membership.sms_reminders_opted_in = True

        # Send consent notice SMS and mark acknowledged (first time only)
        if first_time_opt_in and not membership.sms_fee_acknowledged:
            membership.sms_fee_acknowledged = True
            group_name = group.name if group else "your group"
            currency = group.currency if group else "UGX"
            background_tasks.add_task(
                send_sms_opt_in_consent_notice,
                phone_number=current_user.phone_number,
                member_name=current_user.full_name or "Member",
                group_name=group_name,
                sms_fee=SMS_FEE_UGX,
                currency=currency
            )

    elif request.sms_reminders_opted_in is False:
        membership.sms_reminders_opted_in = False

    if request.sms_reminder_hours_before is not None:
        if not (1 <= request.sms_reminder_hours_before <= 168):
            raise HTTPException(
                status_code=400,
                detail="SMS reminder timing must be between 1 and 168 hours (1 hour to 7 days)."
            )
        membership.sms_reminder_hours_before = request.sms_reminder_hours_before

    # Email reminder preferences
    if request.email_reminders_opted_in is not None:
        membership.email_reminders_opted_in = request.email_reminders_opted_in

    if request.email_reminder_hours_before is not None:
        if not (1 <= request.email_reminder_hours_before <= 168):
            raise HTTPException(
                status_code=400,
                detail="Email reminder timing must be between 1 and 168 hours (1 hour to 7 days)."
            )
        membership.email_reminder_hours_before = request.email_reminder_hours_before

    session.add(membership)
    session.commit()

    currency = group.currency if group else "UGX"
    return {
        "status": "success",
        "message": "Notification preferences updated.",
        "data": {
            "sms_reminders_opted_in": membership.sms_reminders_opted_in,
            "sms_reminder_hours_before": membership.sms_reminder_hours_before,
            "sms_fee_acknowledged": membership.sms_fee_acknowledged,
            "email_reminders_opted_in": membership.email_reminders_opted_in,
            "email_reminder_hours_before": membership.email_reminder_hours_before,
            "fee_notice": (
                f"A {currency} {SMS_FEE_UGX} fee will be added to each deposit you make "
                f"in this group while SMS reminders are enabled."
                if membership.sms_reminders_opted_in else
                "SMS reminders are off. No SMS fees will be charged."
            )
        }
    }
