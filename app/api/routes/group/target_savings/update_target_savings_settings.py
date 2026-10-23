from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.group import GroupMembership
from app.models.user.user import User
from app.models.group.long_term import TargetSavingsGroupDetails
from app.models.group.settings import GroupVisibilitySettings
from .schemas import UpdateTargetSavingsSettingsRequest

router = APIRouter()

@router.patch("/{group_id}/settings", summary="Update Target Savings Group Settings")
def update_target_savings_settings(
    group_id: str,
    request: UpdateTargetSavingsSettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Allows the group Admin to update non-locked settings.
    Settings like target_date and payout_destination_type are locked to protect member funds.
    """
    # 1. Verify Admin
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN",
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Only the Group Admin can update group settings.")

    details = session.exec(
        select(TargetSavingsGroupDetails).where(TargetSavingsGroupDetails.group_id == group_id).with_for_update()
    ).first()
    if not details:
        raise HTTPException(status_code=404, detail="Target savings details not found.")

    if details.is_ended or details.is_paid_out:
        raise HTTPException(status_code=400, detail="Cannot modify settings for an ended savings group.")

    # 2. Apply updates
    if request.contribution_amount is not None:
        details.contribution_amount = request.contribution_amount
    if request.collection_frequency_days is not None:
        details.collection_frequency_days = request.collection_frequency_days
    if request.collection_time is not None:
        details.collection_time = request.collection_time
    if request.require_consensus_at_end is not None:
        details.require_consensus_at_end = request.require_consensus_at_end
    if request.allow_early_payout_by_vote is not None:
        details.allow_early_payout_by_vote = request.allow_early_payout_by_vote
    if request.vote_approval_percentage is not None:
        details.vote_approval_percentage = request.vote_approval_percentage
    if request.enable_late_fees is not None:
        details.enable_late_fees = request.enable_late_fees
    if request.late_fee_amount is not None:
        details.late_fee_amount = request.late_fee_amount
    if request.grace_period_hours is not None:
        details.grace_period_hours = request.grace_period_hours
    if request.missed_payment_action is not None:
        details.missed_payment_action = request.missed_payment_action
    if request.minimum_kyc_tier is not None:
        details.minimum_kyc_tier = request.minimum_kyc_tier
    if request.hide_leaderboard is not None:
        details.hide_leaderboard = request.hide_leaderboard

    # Goal Controls: Lock funds
    locked_val = request.lock_funds if request.lock_funds is not None else request.is_locked
    if locked_val is not None:
        details.is_locked = locked_val

    # Goal Controls: Member total savings visibility
    vis_val = request.let_members_view_total_saved if request.let_members_view_total_saved is not None else request.vis_member_total_savings
    vis = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()
    if vis_val is not None:
        if not vis:
            vis = GroupVisibilitySettings(group_id=group_id)
        vis.vis_member_total_savings = vis_val
        session.add(vis)

    session.add(details)
    session.commit()
    session.refresh(details)
    if vis:
        session.refresh(vis)

    data = details.model_dump(mode="json")
    data["lock_funds"] = details.is_locked
    data["vis_member_total_savings"] = getattr(vis, "vis_member_total_savings", True) if vis else True
    data["let_members_view_total_saved"] = data["vis_member_total_savings"]

    return {
        "status": "success",
        "message": "Target savings settings updated successfully",
        "data": data
    }
