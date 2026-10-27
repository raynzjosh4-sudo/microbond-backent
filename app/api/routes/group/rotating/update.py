from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import Optional
from pydantic import BaseModel, Field
import datetime

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.rotating import RotatingGroupDetails
from app.models.group.settings import GroupFinancialSettings

router = APIRouter()


class UpdateRotatingSettingsRequest(BaseModel):
    # Logistics
    contribution_amount: Optional[float] = Field(default=None, description="Per-collection-interval contribution amount (e.g. 5000 UGX/day)")
    saving_days_per_cycle: Optional[int] = Field(default=None, ge=1, description="Number of saving days per cycle before payout (e.g. 9 days)")
    group_start_time: Optional[int] = Field(default=None, description="Start time epoch timestamp")
    collection_time: Optional[str] = Field(default=None, description="Cutoff time of day (e.g. 18:00)")
    payout_order_strategy: Optional[str] = Field(default=None, description="Randomized by App, Fixed Roster, Admin Decided, Bidding/Auction")
    is_payout_order_locked: Optional[bool] = Field(default=None, description="Freeze payout order schedule")
    
    # Risk controls
    minimum_kyc_tier: Optional[int] = Field(default=None, ge=0, le=3)
    require_guarantor: Optional[bool] = Field(default=None)
    guarantor_default_action: Optional[str] = Field(default=None)
    allow_partial_payments: Optional[bool] = Field(default=None)
    allow_advance_deposits: Optional[bool] = Field(default=None)
    enforce_payout_holds: Optional[bool] = Field(default=None)

    # Settlement & Automation
    auto_disburse_when_full: Optional[bool] = Field(default=None)
    multi_sig_payout_approval: Optional[bool] = Field(default=None)

    # Turn Swaps & Queue Flexibility
    allow_turn_swaps: Optional[bool] = Field(default=None)
    turn_swap_approval_mode: Optional[str] = Field(default=None)

    # Risk Mitigation (Early-Turn Flight Risk)
    early_turn_security_hold_percentage: Optional[float] = Field(default=None)
    require_guarantors_for_early_turns_only: Optional[bool] = Field(default=None)

    # Renewal & Sequencing
    auto_renew_cycle: Optional[bool] = Field(default=None)
    reverse_payout_order_on_renew: Optional[bool] = Field(default=None)

    # Reminders & Automated Collection
    reminder_lead_time_hours: Optional[int] = Field(default=None)
    enable_auto_debit_prompt: Optional[bool] = Field(default=None)

    # Capacity, Frequency & Fees
    maximum_member_capacity: Optional[int] = Field(default=None)
    max_members: Optional[int] = Field(default=None)
    payouts_per_cycle: Optional[int] = Field(default=None)
    payout_per_cycle: Optional[int] = Field(default=None)
    collection_frequency_days: Optional[int] = Field(default=None)
    late_fee_amount: Optional[float] = Field(default=None)
    grace_period_hours: Optional[int] = Field(default=None)



@router.get("/{group_id}/settings/rotating", summary="Get Rotating Group Settings")
@router.get("/{group_id}/settings", summary="Get Rotating Group Settings (Alias)")
def get_rotating_group_settings(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You must be an active member of this group.")

    details = session.exec(
        select(RotatingGroupDetails).where(RotatingGroupDetails.group_id == group_id)
    ).first()
    if not details:
        raise HTTPException(status_code=404, detail="Rotating group details not found.")

    fin_settings = session.exec(
        select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group_id)
    ).first()

    is_cycle_active = bool(details.is_payout_order_locked or group.status == "ACTIVE")
    current_cycle = details.current_cycle or 1
    edit_lock_reason = (
        f"Financial terms cannot be modified because Cycle {current_cycle} is currently active. "
        "The contribution amount, saving days, and rotation rules are locked to protect member deposits "
        "and maintain payout integrity. Terms can only be adjusted between cycles before the next round begins."
    ) if is_cycle_active else None

    return {
        "status": "success",
        "data": {
            "group_id": group_id,
            "group_name": group.name,
            "is_admin": membership.role == "ADMIN",
            "is_cycle_active": is_cycle_active,
            "is_financial_editable": not is_cycle_active,
            "edit_lock_reason": edit_lock_reason,
            "contribution_amount": details.contribution_amount,
            "saving_days_per_cycle": details.saving_days_per_cycle,
            "payouts_per_cycle": details.payouts_per_cycle,
            "number_of_cycles": details.number_of_cycles,
            "collection_frequency_days": details.collection_frequency_days,
            "collection_time": details.collection_time,
            "group_start_time": details.group_start_time,
            "payout_order_strategy": details.payout_order_strategy,
            "is_payout_order_locked": details.is_payout_order_locked,
            "total_expected_pool_per_cycle": details.total_expected_pool_per_cycle,
            "minimum_kyc_tier": details.minimum_kyc_tier,
            "require_guarantor": details.require_guarantor,
            "guarantor_default_action": details.guarantor_default_action,
            "allow_partial_payments": details.allow_partial_payments,
            "allow_advance_deposits": details.allow_advance_deposits,
            "enforce_payout_holds": fin_settings.enforce_payout_holds if fin_settings else False,
            "auto_disburse_when_full": details.auto_disburse_when_full,
            "multi_sig_payout_approval": details.multi_sig_payout_approval,
            "allow_turn_swaps": details.allow_turn_swaps,
            "turn_swap_approval_mode": details.turn_swap_approval_mode,
            "early_turn_security_hold_percentage": details.early_turn_security_hold_percentage,
            "require_guarantors_for_early_turns_only": details.require_guarantors_for_early_turns_only,
            "auto_renew_cycle": details.auto_renew_cycle,
            "reverse_payout_order_on_renew": details.reverse_payout_order_on_renew,
            "reminder_lead_time_hours": details.reminder_lead_time_hours,
            "enable_auto_debit_prompt": details.enable_auto_debit_prompt,
            "current_cycle": details.current_cycle,
            "current_saving_day": details.current_saving_day,
            "maximum_member_capacity": group.max_members,
            "max_members": group.max_members,
            "payouts_per_cycle": details.payouts_per_cycle,
            "payout_per_cycle": details.payouts_per_cycle,
            "late_fee_amount": fin_settings.late_fee_amount if fin_settings else 0.0,
            "grace_period_hours": fin_settings.grace_period_hours if fin_settings else 0,
        }
    }



@router.put("/{group_id}/settings/rotating", summary="Update Rotating Group Settings")
@router.patch("/{group_id}/settings/rotating", summary="Partial Update Rotating Group Settings")
@router.patch("/{group_id}/settings", summary="Update Rotating Group Settings (Alias)")
def update_rotating_group_settings(
    group_id: str,
    request: UpdateRotatingSettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")
        
    admin_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN",
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    
    if not admin_membership:
        raise HTTPException(status_code=403, detail="Only the Group Admin can update settings.")

    details = session.exec(
        select(RotatingGroupDetails).where(RotatingGroupDetails.group_id == group_id)
    ).first()
    if not details:
        raise HTTPException(status_code=404, detail="Rotating group details not found.")
    
    # 1. Active Cycle Lock Enforcement: When a cycle is on, no one can change financial terms
    is_cycle_active = bool(details.is_payout_order_locked or group.status == "ACTIVE")
    if is_cycle_active:
        current_cycle = details.current_cycle or 1
        locked_changes = []

        if request.collection_frequency_days is not None and request.collection_frequency_days != details.collection_frequency_days:
            locked_changes.append("collection_frequency_days")
        if request.collection_time is not None and request.collection_time != details.collection_time:
            locked_changes.append("collection_time")
        if request.group_start_time is not None and request.group_start_time != details.group_start_time:
            locked_changes.append("group_start_time")
        if request.contribution_amount is not None and request.contribution_amount != details.contribution_amount:
            locked_changes.append("contribution_amount")
        if request.saving_days_per_cycle is not None and request.saving_days_per_cycle != details.saving_days_per_cycle:
            locked_changes.append("saving_days_per_cycle")

        cap = request.maximum_member_capacity if request.maximum_member_capacity is not None else request.max_members
        if cap is not None and cap != group.max_members:
            locked_changes.append("member_capacity")

        payout_val = request.payouts_per_cycle if request.payouts_per_cycle is not None else request.payout_per_cycle
        if payout_val is not None and payout_val != details.payouts_per_cycle:
            locked_changes.append("payouts_per_cycle")

        if request.payout_order_strategy is not None and request.payout_order_strategy != details.payout_order_strategy:
            locked_changes.append("payout_order_strategy")
        if request.early_turn_security_hold_percentage is not None and request.early_turn_security_hold_percentage != details.early_turn_security_hold_percentage:
            locked_changes.append("early_turn_security_hold_percentage")
        if request.auto_disburse_when_full is not None and request.auto_disburse_when_full != details.auto_disburse_when_full:
            locked_changes.append("auto_disburse_when_full")
        if request.multi_sig_payout_approval is not None and request.multi_sig_payout_approval != details.multi_sig_payout_approval:
            locked_changes.append("multi_sig_payout_approval")

        if locked_changes:
            human_fields = ", ".join(f.replace("_", " ") for f in locked_changes)
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Settings [{human_fields}] cannot be modified because Cycle {current_cycle} is currently active. "
                    "Collection frequency, contribution amounts, saving days, and core rotation schedules are locked "
                    "to protect member deposits and maintain schedule integrity. Adjustments can only be made between "
                    "cycles before the next round begins. (Allowed mid-cycle adjustments: turn swaps, guarantors, "
                    "KYC tier, partial payments, advance deposits, late fees, and grace period)."
                )
            )

    if request.contribution_amount is not None:
        details.contribution_amount = request.contribution_amount
        # Sync all un-paid obligations so the deposit process immediately reflects the updated amount
        from app.models.group.finance import MemberObligation
        pending_obs = session.exec(
            select(MemberObligation).where(
                MemberObligation.group_id == group_id,
                MemberObligation.amount_paid == 0
            )
        ).all()
        for ob in pending_obs:
            ob.amount_due = request.contribution_amount
            session.add(ob)

        # Recalculate pool: contribution * saving_days * members
        saving_days = details.saving_days_per_cycle or 1
        if group.max_members:
            details.total_expected_pool_per_cycle = request.contribution_amount * saving_days * group.max_members

    if request.saving_days_per_cycle is not None:
        details.saving_days_per_cycle = request.saving_days_per_cycle
        # Recalculate pool with updated saving days
        contribution = details.contribution_amount or 0
        if group.max_members and contribution > 0:
            details.total_expected_pool_per_cycle = contribution * request.saving_days_per_cycle * group.max_members
            
    if request.group_start_time is not None:
        start_ms = request.group_start_time
        if start_ms < 100000000000:
            start_ms = start_ms * 1000
        details.group_start_time = start_ms
        
    if request.collection_time is not None:
        details.collection_time = request.collection_time
    if request.payout_order_strategy is not None:
        details.payout_order_strategy = request.payout_order_strategy
    if request.is_payout_order_locked is not None:
        details.is_payout_order_locked = request.is_payout_order_locked
    if request.minimum_kyc_tier is not None:
        details.minimum_kyc_tier = request.minimum_kyc_tier
    if request.require_guarantor is not None:
        details.require_guarantor = request.require_guarantor
    if request.guarantor_default_action is not None:
        details.guarantor_default_action = request.guarantor_default_action
    if request.allow_partial_payments is not None:
        details.allow_partial_payments = request.allow_partial_payments
    if request.allow_advance_deposits is not None:
        details.allow_advance_deposits = request.allow_advance_deposits
        
    fin_settings = session.exec(
        select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group_id)
    ).first()
    if request.enforce_payout_holds is not None and fin_settings:
        fin_settings.enforce_payout_holds = request.enforce_payout_holds
        session.add(fin_settings)

    if request.auto_disburse_when_full is not None:
        details.auto_disburse_when_full = request.auto_disburse_when_full
    if request.multi_sig_payout_approval is not None:
        details.multi_sig_payout_approval = request.multi_sig_payout_approval
    if request.allow_turn_swaps is not None:
        details.allow_turn_swaps = request.allow_turn_swaps
    if request.turn_swap_approval_mode is not None:
        details.turn_swap_approval_mode = request.turn_swap_approval_mode
    if request.early_turn_security_hold_percentage is not None:
        details.early_turn_security_hold_percentage = request.early_turn_security_hold_percentage
    if request.require_guarantors_for_early_turns_only is not None:
        details.require_guarantors_for_early_turns_only = request.require_guarantors_for_early_turns_only
    if request.auto_renew_cycle is not None:
        details.auto_renew_cycle = request.auto_renew_cycle
    if request.reverse_payout_order_on_renew is not None:
        details.reverse_payout_order_on_renew = request.reverse_payout_order_on_renew
    if request.reminder_lead_time_hours is not None:
        details.reminder_lead_time_hours = request.reminder_lead_time_hours
    if request.enable_auto_debit_prompt is not None:
        details.enable_auto_debit_prompt = request.enable_auto_debit_prompt

    # Capacity & Member Limits
    cap = request.maximum_member_capacity if request.maximum_member_capacity is not None else request.max_members
    if cap is not None:
        group.max_members = cap
        session.add(group)
        if details.contribution_amount:
            saving_days = details.saving_days_per_cycle or 1
            details.total_expected_pool_per_cycle = details.contribution_amount * saving_days * cap
        if details.payouts_per_cycle:
            import math
            details.number_of_cycles = math.ceil(cap / details.payouts_per_cycle)

    # Payouts per cycle
    payout_val = request.payouts_per_cycle if request.payouts_per_cycle is not None else request.payout_per_cycle
    if payout_val is not None:
        details.payouts_per_cycle = payout_val
        if group.max_members:
            import math
            details.number_of_cycles = math.ceil(group.max_members / payout_val)

    if request.collection_frequency_days is not None:
        details.collection_frequency_days = request.collection_frequency_days

    if fin_settings:
        if request.late_fee_amount is not None:
            fin_settings.late_fee_amount = request.late_fee_amount
            session.add(fin_settings)
        if request.grace_period_hours is not None:
            fin_settings.grace_period_hours = request.grace_period_hours
            session.add(fin_settings)

    session.add(details)
    session.commit()
    session.refresh(details)
    return {
        "status": "success",
        "message": "Rotating specific settings updated successfully.",
        "data": {
            "contribution_amount": details.contribution_amount,
            "saving_days_per_cycle": details.saving_days_per_cycle,
            "payout_order_strategy": details.payout_order_strategy,
            "is_payout_order_locked": details.is_payout_order_locked,
            "require_guarantor": details.require_guarantor,
            "allow_partial_payments": details.allow_partial_payments,
            "allow_advance_deposits": details.allow_advance_deposits,
            "enforce_payout_holds": fin_settings.enforce_payout_holds if fin_settings else False,
            "auto_disburse_when_full": details.auto_disburse_when_full,
            "multi_sig_payout_approval": details.multi_sig_payout_approval,
            "allow_turn_swaps": details.allow_turn_swaps,
            "turn_swap_approval_mode": details.turn_swap_approval_mode,
            "early_turn_security_hold_percentage": details.early_turn_security_hold_percentage,
            "require_guarantors_for_early_turns_only": details.require_guarantors_for_early_turns_only,
            "auto_renew_cycle": details.auto_renew_cycle,
            "reverse_payout_order_on_renew": details.reverse_payout_order_on_renew,
            "reminder_lead_time_hours": details.reminder_lead_time_hours,
            "enable_auto_debit_prompt": details.enable_auto_debit_prompt,
            "maximum_member_capacity": group.max_members,
            "max_members": group.max_members,
            "payouts_per_cycle": details.payouts_per_cycle,
            "payout_per_cycle": details.payouts_per_cycle,
            "number_of_cycles": details.number_of_cycles,
            "collection_frequency_days": details.collection_frequency_days,
            "collection_time": details.collection_time,
            "group_start_time": details.group_start_time,
            "late_fee_amount": fin_settings.late_fee_amount if fin_settings else 0.0,
            "grace_period_hours": fin_settings.grace_period_hours if fin_settings else 0,
            "total_expected_pool_per_cycle": details.total_expected_pool_per_cycle,
            "current_saving_day": details.current_saving_day
        }
    }


