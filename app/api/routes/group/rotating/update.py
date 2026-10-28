from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
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
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from app.services.websocket_manager import ws_manager

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
    minimum_partial_payment_amount: Optional[float] = Field(default=None, ge=0, description="Minimum UGX amount a member must pay per deposit when partial payments are on. Set to 0 to remove floor.")
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

    is_cycle_active = bool(details.is_payout_order_locked)
    current_cycle = details.current_cycle or 1

    return {
        "status": "success",
        "data": {
            "group_id": group_id,
            "group_name": group.name,
            "is_admin": membership.role == "ADMIN",
            "is_cycle_active": is_cycle_active,
            "is_financial_editable": True,
            "edit_lock_reason": None,
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
            "minimum_partial_payment_amount": details.minimum_partial_payment_amount,
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
    background_tasks: BackgroundTasks = BackgroundTasks(),
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

    fin_settings = session.exec(
        select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group_id)
    ).first()

    admin_name = current_user.full_name or "Admin"
    current_cycle = details.current_cycle or 1
    change_notices = []

    # 1. Financial & Contribution Terms (Admins can update even while group is running)
    if request.contribution_amount is not None and request.contribution_amount != details.contribution_amount:
        old_amt = int(details.contribution_amount or 0)
        new_amt = int(request.contribution_amount)
        details.contribution_amount = request.contribution_amount
        # Sync all un-paid obligations for the current cycle so deposit sheet immediately reflects the new amount
        from app.models.group.finance import MemberObligation
        pending_obs = session.exec(
            select(MemberObligation).where(
                MemberObligation.group_id == group_id,
                MemberObligation.cycle_number == current_cycle,
                MemberObligation.amount_paid == 0
            )
        ).all()
        for ob in pending_obs:
            ob.amount_due = request.contribution_amount
            session.add(ob)

        saving_days = details.saving_days_per_cycle or 1
        if group.max_members:
            details.total_expected_pool_per_cycle = request.contribution_amount * saving_days * group.max_members

        change_notices.append(
            f"Contribution Amount changed from UGX {old_amt:,} to UGX {new_amt:,}. "
            f"All unpaid obligations for Cycle {current_cycle} and future cycles are updated to UGX {new_amt:,}."
        )

    if request.saving_days_per_cycle is not None and request.saving_days_per_cycle != details.saving_days_per_cycle:
        old_days = details.saving_days_per_cycle or 1
        new_days = request.saving_days_per_cycle
        details.saving_days_per_cycle = new_days
        contribution = details.contribution_amount or 0
        if group.max_members and contribution > 0:
            details.total_expected_pool_per_cycle = contribution * new_days * group.max_members
        change_notices.append(
            f"Cycle Duration changed from {old_days} to {new_days} saving days per round. Payouts will now occur every {new_days} saving days."
        )

    if request.group_start_time is not None and request.group_start_time != details.group_start_time:
        start_ms = request.group_start_time
        if start_ms < 100000000000:
            start_ms = start_ms * 1000
        details.group_start_time = start_ms
        change_notices.append("Group start schedule timestamp updated.")

    if request.collection_time is not None and request.collection_time != details.collection_time:
        details.collection_time = request.collection_time
        change_notices.append(
            f"Daily Contribution Deadline set to {request.collection_time}. Deposits submitted after this time fall into the grace period."
        )

    if request.collection_frequency_days is not None and request.collection_frequency_days != details.collection_frequency_days:
        details.collection_frequency_days = request.collection_frequency_days
        change_notices.append(
            f"Collection Frequency updated to every {request.collection_frequency_days} days."
        )

    if request.payout_order_strategy is not None and request.payout_order_strategy != details.payout_order_strategy:
        details.payout_order_strategy = request.payout_order_strategy
        change_notices.append(
            f"Payout Order Strategy updated to '{request.payout_order_strategy}'."
        )

    if request.is_payout_order_locked is not None and request.is_payout_order_locked != details.is_payout_order_locked:
        details.is_payout_order_locked = request.is_payout_order_locked
        if request.is_payout_order_locked:
            change_notices.append("Payout schedule order is now locked.")
        else:
            change_notices.append("Payout schedule order has been unlocked for adjustments.")

    # 2. Risk Controls & Payment Flexibility
    if request.allow_partial_payments is not None and request.allow_partial_payments != details.allow_partial_payments:
        details.allow_partial_payments = request.allow_partial_payments
        min_amt = int(details.minimum_partial_payment_amount or 1000)
        base_amt = int(details.contribution_amount or 0)
        if request.allow_partial_payments:
            change_notices.append(
                f"Partial Payments enabled (minimum deposit: UGX {min_amt:,}). Members can now contribute their cycle obligation in installments."
            )
        else:
            change_notices.append(
                f"Partial Payments disabled. Members must now contribute the full cycle amount of UGX {base_amt:,} in a single deposit."
            )

    if request.minimum_partial_payment_amount is not None and request.minimum_partial_payment_amount != details.minimum_partial_payment_amount:
        details.minimum_partial_payment_amount = request.minimum_partial_payment_amount
        change_notices.append(
            f"Minimum Partial Deposit updated to UGX {int(request.minimum_partial_payment_amount):,}. Partial payments below this amount will not be accepted."
        )

    if request.allow_advance_deposits is not None and request.allow_advance_deposits != details.allow_advance_deposits:
        details.allow_advance_deposits = request.allow_advance_deposits
        if request.allow_advance_deposits:
            change_notices.append(
                "Advance Deposits enabled. Overpayments will be credited as prepaid savings toward upcoming cycles."
            )
        else:
            change_notices.append(
                "Advance Deposits disabled. Members can only deposit their remaining cycle obligation."
            )

    if request.enforce_payout_holds is not None and fin_settings:
        fin_settings.enforce_payout_holds = request.enforce_payout_holds
        session.add(fin_settings)
        if request.enforce_payout_holds:
            change_notices.append("Payout holds enabled. Defaulters will have payouts suspended until arrears are cleared.")
        else:
            change_notices.append("Payout holds disabled.")

    if fin_settings:
        if request.late_fee_amount is not None and request.late_fee_amount != fin_settings.late_fee_amount:
            fin_settings.late_fee_amount = request.late_fee_amount
            session.add(fin_settings)
            change_notices.append(
                f"Late-fee penalty updated to UGX {int(request.late_fee_amount):,}. Applies to overdue contributions after grace period expires."
            )
        if request.grace_period_hours is not None and request.grace_period_hours != fin_settings.grace_period_hours:
            fin_settings.grace_period_hours = request.grace_period_hours
            session.add(fin_settings)
            change_notices.append(
                f"Grace period updated to {request.grace_period_hours} hours after the deadline before late fees and arrears apply."
            )

    # 3. Turn Swaps & Guarantors
    if request.allow_turn_swaps is not None and request.allow_turn_swaps != details.allow_turn_swaps:
        details.allow_turn_swaps = request.allow_turn_swaps
        if request.allow_turn_swaps:
            change_notices.append("Payout Turn Swaps enabled. Members can now request to swap payout turns with each other.")
        else:
            change_notices.append("Payout Turn Swaps disabled. Payout positions are now fixed.")

    if request.turn_swap_approval_mode is not None and request.turn_swap_approval_mode != details.turn_swap_approval_mode:
        details.turn_swap_approval_mode = request.turn_swap_approval_mode
        change_notices.append(f"Turn swap approval mode set to '{request.turn_swap_approval_mode}'.")

    if request.require_guarantor is not None and request.require_guarantor != details.require_guarantor:
        details.require_guarantor = request.require_guarantor
        if request.require_guarantor:
            change_notices.append("Guarantor requirement enabled. Members must be vouched for by an active member before receiving payouts.")
        else:
            change_notices.append("Guarantor requirement removed.")

    if request.guarantor_default_action is not None and request.guarantor_default_action != details.guarantor_default_action:
        details.guarantor_default_action = request.guarantor_default_action
        change_notices.append(f"Guarantor default action set to '{request.guarantor_default_action}'.")

    if request.minimum_kyc_tier is not None and request.minimum_kyc_tier != details.minimum_kyc_tier:
        details.minimum_kyc_tier = request.minimum_kyc_tier
        change_notices.append(f"Identity verification requirement set to Tier {request.minimum_kyc_tier}.")

    if request.early_turn_security_hold_percentage is not None and request.early_turn_security_hold_percentage != details.early_turn_security_hold_percentage:
        details.early_turn_security_hold_percentage = request.early_turn_security_hold_percentage
        change_notices.append(f"Early-turn security hold set to {request.early_turn_security_hold_percentage}%.")

    if request.require_guarantors_for_early_turns_only is not None and request.require_guarantors_for_early_turns_only != details.require_guarantors_for_early_turns_only:
        details.require_guarantors_for_early_turns_only = request.require_guarantors_for_early_turns_only
        if request.require_guarantors_for_early_turns_only:
            change_notices.append("Guarantor requirement restricted to early turns only.")
        else:
            change_notices.append("Guarantor requirement applies to all turns.")

    # 4. Automation & Renewals
    if request.auto_disburse_when_full is not None and request.auto_disburse_when_full != details.auto_disburse_when_full:
        details.auto_disburse_when_full = request.auto_disburse_when_full
        if request.auto_disburse_when_full:
            change_notices.append("Automatic disbursement enabled. Payouts will disburse automatically when collections reach 100%.")
        else:
            change_notices.append("Automatic disbursement disabled. Payouts require manual Admin release.")

    if request.multi_sig_payout_approval is not None and request.multi_sig_payout_approval != details.multi_sig_payout_approval:
        details.multi_sig_payout_approval = request.multi_sig_payout_approval
        if request.multi_sig_payout_approval:
            change_notices.append("Multi-signature payout approval enabled. Payouts must be approved by designated signers.")
        else:
            change_notices.append("Multi-signature payout approval disabled.")

    if request.auto_renew_cycle is not None and request.auto_renew_cycle != details.auto_renew_cycle:
        details.auto_renew_cycle = request.auto_renew_cycle
        if request.auto_renew_cycle:
            change_notices.append("Automatic cycle renewal enabled. The circle will immediately start a new round after the final payout.")
        else:
            change_notices.append("Automatic cycle renewal disabled.")

    if request.reverse_payout_order_on_renew is not None and request.reverse_payout_order_on_renew != details.reverse_payout_order_on_renew:
        details.reverse_payout_order_on_renew = request.reverse_payout_order_on_renew
        if request.reverse_payout_order_on_renew:
            change_notices.append("Payout order reversal on renewal enabled. Turn order will flip in the next round.")
        else:
            change_notices.append("Payout order reversal on renewal disabled.")

    if request.reminder_lead_time_hours is not None and request.reminder_lead_time_hours != details.reminder_lead_time_hours:
        details.reminder_lead_time_hours = request.reminder_lead_time_hours
        change_notices.append(f"Reminder lead time set to {request.reminder_lead_time_hours} hours before collection deadline.")

    if request.enable_auto_debit_prompt is not None and request.enable_auto_debit_prompt != details.enable_auto_debit_prompt:
        details.enable_auto_debit_prompt = request.enable_auto_debit_prompt
        if request.enable_auto_debit_prompt:
            change_notices.append("Automated contribution payment prompts enabled.")
        else:
            change_notices.append("Automated contribution payment prompts disabled.")

    # Capacity & Member Limits
    cap = request.maximum_member_capacity if request.maximum_member_capacity is not None else request.max_members
    if cap is not None and cap != group.max_members:
        group.max_members = cap
        session.add(group)
        if details.contribution_amount:
            saving_days = details.saving_days_per_cycle or 1
            details.total_expected_pool_per_cycle = details.contribution_amount * saving_days * cap
        if details.payouts_per_cycle:
            import math
            details.number_of_cycles = math.ceil(cap / details.payouts_per_cycle)
        change_notices.append(f"Maximum member capacity updated to {cap} members.")

    payout_val = request.payouts_per_cycle if request.payouts_per_cycle is not None else request.payout_per_cycle
    if payout_val is not None and payout_val != details.payouts_per_cycle:
        details.payouts_per_cycle = payout_val
        if group.max_members:
            import math
            details.number_of_cycles = math.ceil(group.max_members / payout_val)
        change_notices.append(f"Payouts per cycle set to {payout_val} recipient(s) per round.")

    session.add(details)
    session.commit()
    session.refresh(details)

    # Broadcast system message and real-time WebSocket event explaining what changed and what will happen
    if change_notices:
        bullet_points = "\n".join(f"• {c}" for c in change_notices)
        system_text = f"⚙️ Group Settings Updated by {admin_name}:\n{bullet_points}"
        system_msg = broadcast_system_message_sync(
            group_id=group_id,
            message_text=system_text,
            message_type="SYSTEM_EVENT",
            sender_id="SYSTEM",
            session=session,
            background_tasks=background_tasks,
            attachments=[{
                "category": "SETTINGS_UPDATE",
                "setting_type": "ROTATING",
                "admin_id": str(current_user.id),
                "admin_name": admin_name,
                "changes_count": len(change_notices)
            }]
        )
        if background_tasks is None and system_msg:
            try:
                import asyncio
                asyncio.create_task(
                    ws_manager.broadcast_to_group(
                        group_id,
                        {
                            "event_type": "NEW_MESSAGE",
                            "message": system_msg.model_dump(mode="json")
                        }
                    )
                )
            except Exception:
                pass
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
            "minimum_partial_payment_amount": details.minimum_partial_payment_amount,
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


