import time

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.models.group.core.group import Group
from app.models.group.core.group_membership import GroupMembership
from app.models.group.settings import (
    GroupFinancialSettings,
    GroupGovernanceSettings,
    GroupVisibilitySettings,
)
from app.models.group.target_savings import TargetSavingsGroupDetails
from app.models.user.user import User
from .schemas import UpdateTargetSavingsSettingsRequest

router = APIRouter()


@router.patch("/{group_id}/settings", summary="Update Target Savings Group Settings")
def update_target_savings_settings(
    group_id: str,
    request: UpdateTargetSavingsSettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN",
            GroupMembership.status == "ACTIVE",
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Only an active group admin can update settings.")

    group = session.exec(
        select(Group).where(Group.group_id == group_id).with_for_update()
    ).first()
    if not group or group.type != "GOAL_SAVINGS":
        raise HTTPException(status_code=404, detail="Target savings group not found.")

    details = session.exec(
        select(TargetSavingsGroupDetails)
        .where(TargetSavingsGroupDetails.group_id == group_id)
        .with_for_update()
    ).first()
    if not details:
        raise HTTPException(status_code=404, detail="Target savings details not found.")

    update = request.model_dump(exclude_unset=True)
    if not update:
        return {"status": "success", "message": "No settings changed.", "data": details.model_dump(mode="json")}

    allow_max_members = update.get("allow_max_members", group.max_members is not None)
    max_members = update.get("max_members", group.max_members)
    if allow_max_members and (max_members is None or max_members < 2):
        raise HTTPException(
            status_code=400,
            detail="A maximum member count of at least 2 is required when the member limit is enabled.",
        )
    if allow_max_members and max_members < group.member_count:
        raise HTTPException(
            status_code=400,
            detail="The member limit cannot be lower than the current group member count.",
        )
    group.max_members = max_members if allow_max_members else None

    allow_amount = update.get("allow_target_amount", details.allow_target_amount)
    amount = update.get("target_amount", details.target_amount)
    if allow_amount:
        if amount is None or amount <= 0:
            raise HTTPException(status_code=400, detail="A positive target amount is required when enabled.")
    else:
        amount = None

    allow_date = update.get("allow_target_date", details.allow_target_date)
    target_date = update.get("target_date", details.target_date)
    if allow_date:
        if target_date is None or target_date <= int(time.time() * 1000):
            raise HTTPException(status_code=400, detail="A future target date is required when enabled.")
    else:
        target_date = None

    allow_schedule = update.get(
        "allow_contribution_schedule", details.allow_contribution_schedule
    )
    contribution_amount = update.get("contribution_amount", details.contribution_amount)
    if allow_schedule:
        if contribution_amount is None or contribution_amount <= 0:
            raise HTTPException(
                status_code=400,
                detail="A positive contribution amount is required when the schedule is enabled.",
            )
    else:
        contribution_amount = 0

    allow_frequency = update.get(
        "allow_collection_frequency", details.allow_collection_frequency
    )
    frequency_days = update.get(
        "collection_frequency_days", details.collection_frequency_days
    )
    if allow_frequency:
        if not allow_schedule:
            raise HTTPException(
                status_code=400,
                detail="Collection frequency requires an enabled contribution schedule.",
            )
        if frequency_days is None or frequency_days <= 0:
            raise HTTPException(
                status_code=400,
                detail="A positive collection frequency is required when enabled.",
            )
    else:
        frequency_days = 0

    enable_late_fees = update.get("enable_late_fees", details.enable_late_fees)
    late_fee_amount = update.get("late_fee_amount", details.late_fee_amount)
    if enable_late_fees:
        if not allow_frequency:
            raise HTTPException(
                status_code=400,
                detail="Late fees require an enabled contribution frequency.",
            )
        if late_fee_amount is None or late_fee_amount <= 0:
            raise HTTPException(
                status_code=400,
                detail="A positive late fee amount is required when late fees are enabled.",
            )
    else:
        late_fee_amount = 0

    if "allow_multi_payout" in update and update["allow_multi_payout"] != details.allow_multi_payout:
        if group.total_balance:
            raise HTTPException(
                status_code=409,
                detail="Payout mode cannot change while the group holds contributed funds.",
            )
        details.allow_multi_payout = update["allow_multi_payout"]
        details.payout_destination_type = (
            "PROPORTIONAL_RETURN"
            if details.allow_multi_payout
            else "SINGLE_NOMINATED_ACCOUNT"
        )
        details.nominated_account_id = None

    details.allow_target_amount = allow_amount
    details.target_amount = amount
    details.allow_target_date = allow_date
    details.target_date = target_date
    details.allow_contribution_schedule = allow_schedule
    details.contribution_amount = contribution_amount
    details.allow_collection_frequency = allow_frequency
    details.collection_frequency_days = frequency_days
    if "collection_time" in update:
        details.collection_time = update["collection_time"]
    if not allow_frequency:
        details.collection_time = None

    details.enable_late_fees = enable_late_fees
    details.late_fee_amount = late_fee_amount
    financial_settings = session.exec(
        select(GroupFinancialSettings)
        .where(GroupFinancialSettings.group_id == group_id)
        .with_for_update()
    ).first()
    if financial_settings:
        financial_settings.enable_late_fees = enable_late_fees
        financial_settings.late_fee_amount = float(late_fee_amount)
        financial_settings.grace_period_hours = update.get(
            "grace_period_hours",
            details.grace_period_hours,
        )
        session.add(financial_settings)
    for field in (
        "require_consensus_at_end",
        "allow_early_payout_by_vote",
        "vote_approval_percentage",
        "grace_period_hours",
        "missed_payment_action",
        "minimum_kyc_tier",
        "hide_leaderboard",
    ):
        if field in update:
            setattr(details, field, update[field])

    if "minimum_kyc_tier" in update:
        governance_settings = session.exec(
            select(GroupGovernanceSettings)
            .where(GroupGovernanceSettings.group_id == group_id)
            .with_for_update()
        ).first()
        if governance_settings:
            governance_settings.minimum_kyc_tier = update["minimum_kyc_tier"]
            session.add(governance_settings)

    lock_value = update.get("lock_funds", update.get("is_locked"))
    if lock_value is not None:
        details.is_locked = lock_value

    visibility_value = update.get(
        "let_members_view_total_saved",
        update.get("vis_member_total_savings"),
    )
    visibility = session.exec(
        select(GroupVisibilitySettings)
        .where(GroupVisibilitySettings.group_id == group_id)
        .with_for_update()
    ).first()
    if visibility_value is not None:
        if not visibility:
            visibility = GroupVisibilitySettings(group_id=group_id)
        visibility.vis_member_total_savings = visibility_value
        session.add(visibility)

    session.add(details)
    session.commit()
    session.refresh(details)
    if visibility:
        session.refresh(visibility)

    response_data = details.model_dump(mode="json")
    response_data["lock_funds"] = details.is_locked
    response_data["vis_member_total_savings"] = (
        visibility.vis_member_total_savings if visibility else True
    )
    response_data["let_members_view_total_saved"] = response_data["vis_member_total_savings"]
    response_data["allow_max_members"] = group.max_members is not None
    response_data["max_members"] = group.max_members
    response_data["start_date"] = group.start_date

    return {
        "status": "success",
        "message": "Target savings settings updated successfully.",
        "data": response_data,
    }
