"""
rotating_surplus_credit_manager.py
─────────────────────────────────────────────────────────────────────────────
Rotating Group (MERRY_GO_ROUND / ROSCA) — Surplus Credit & Advance Engine

WHAT THIS MODULE SOLVES:
  When a member contributes more than their current cycle obligation (e.g.,
  sending 150,000 UGX when 50,000 UGX is due in Cycle 3), this engine answers:

    1. ALLOCATION WATERFALL (Branch 1A):
       How does the extra 100,000 UGX attach to future cycles?
       → Strict chronological FIFO (Cycle 4, then Cycle 5).
       → In a ROSCA, members CANNOT cherry-pick or skip cycles (e.g.,
         "apply to Cycle 10"), because skipping a cycle deprives that cycle's
         scheduled recipient of their full pooled pot.

    2. DYNAMIC REVALUATION ON CONTRIBUTION CHANGE (Branch 1B):
       If the group votes to increase contributions (e.g., 50k to 60k UGX),
       what happens to prepaid credit?
       → Credit is stored as raw UGX cash value, not abstract "cycle tokens".
       → Re-evaluates coverage against the new rate, identifying exact
         cycle coverage and any residual shortfall the user must top up.

    3. SOCIAL PRIVACY VS. TRANSPARENCY (Branch 2C & 2D):
       How are overpayments broadcast to the group chat?
       → Group chat receives only standard obligation settlement confirmation.
       → Advance runway is kept strictly private to protect members from
         communal borrowing pressure or jealousy.
       → Payout queue position is NEVER altered by prepayments (turn invariance).

    4. ACCIDENTAL OVERPAYMENT REFUNDS & MULTI-SIG SAFEGUARDS (Branch 3E & 3F):
       What if a user accidentally types an extra zero (e.g., sends 500,000 UGX)?
       → Unallocated advance credit can be refunded (unlike current-cycle pot money).
       → Requires 4 security gates:
           a. Liquidity buffer check (cannot deplete upcoming recipient pot)
           b. Multi-sig admin/treasurer approval
           c. Cooldown timelock (prevents rapid transit laundering)
           d. Outgoing telecom fee netting (group/platform absorbs 0 UGX).

USAGE:
  from app.api.routes.group.rotating.rotatingdepositwithdrawfeecalculation import (
      allocate_surplus_to_future_cycles,
      recalculate_credit_on_contribution_change,
      validate_surplus_withdrawal,
      format_deposit_broadcast_message,
  )
─────────────────────────────────────────────────────────────────────────────
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Union


# ── Enums ──────────────────────────────────────────────────────────────────

class CoverageStatus(str, Enum):
    """Status of a future cycle obligation relative to advance credit."""
    FULLY_COVERED     = "FULLY_COVERED"     # 100% satisfied by advance credit
    PARTIALLY_COVERED = "PARTIALLY_COVERED" # Partially covered; deficit remaining
    UNCOVERED         = "UNCOVERED"         # No credit reached this cycle


class WithdrawalEligibilityStatus(str, Enum):
    """Result of evaluating an accidental overpayment refund request."""
    ELIGIBLE                = "ELIGIBLE"                # All gates passed; ready to disburse
    EXCEEDS_CREDIT_BALANCE  = "EXCEEDS_CREDIT_BALANCE"  # Requested > unallocated advance credit
    INSUFFICIENT_POOL_CASH  = "INSUFFICIENT_POOL_CASH"  # Withdrawal would break upcoming recipient pot
    TIMELOCK_ACTIVE         = "TIMELOCK_ACTIVE"         # Cooldown window has not expired
    PENDING_APPROVALS       = "PENDING_APPROVALS"       # Multi-sig approvals still required
    BELOW_MINIMUM_THRESHOLD = "BELOW_MINIMUM_THRESHOLD" # Amount less than telecom disbursement fee


# ── Data Models ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CycleCoverageDetail:
    """Breakdown of how advance credit applies to a specific cycle."""
    cycle_number: int
    amount_required: int
    amount_allocated: int
    shortfall: int
    status: CoverageStatus


@dataclass(frozen=True)
class SurplusAllocationResult:
    """
    Authoritative result of allocating surplus funds across future cycles.
    """
    total_surplus_ugx: int
    cycles_fully_covered_count: int
    fully_covered_cycles: List[int]
    partially_covered_cycle: Optional[CycleCoverageDetail]
    unallocated_residual_ugx: int
    next_cycle_requiring_payment: int
    coverage_breakdown: List[CycleCoverageDetail]
    summary_label: str


@dataclass(frozen=True)
class ContributionAdjustmentResult:
    """
    Result of re-evaluating existing advance credit when the group votes
    to change its standard contribution amount.
    """
    existing_credit_balance_ugx: int
    old_contribution_amount_ugx: int
    new_contribution_amount_ugx: int
    new_cycles_fully_covered: int
    partial_cycle_number: Optional[int]
    partial_cycle_credit_applied: int
    partial_cycle_shortfall: int
    user_advisory_message: str


@dataclass(frozen=True)
class SurplusWithdrawalEvaluation:
    """
    Security and liquidity validation for accidental overpayment refunds.
    """
    status: WithdrawalEligibilityStatus
    is_eligible: bool
    requested_amount_ugx: int
    approved_gross_amount_ugx: int
    telecom_disbursement_fee_ugx: int
    net_payout_to_member_ugx: int
    remaining_credit_after_refund: int
    group_pool_balance_after_refund: int
    reason_message: str


# ── Branch 1A: Chronological FIFO Waterfall Allocation ─────────────────────

def allocate_surplus_to_future_cycles(
    surplus_amount_ugx: int,
    current_cycle_number: int,
    standard_contribution_amount: int,
    cycle_specific_obligations: Optional[Dict[int, int]] = None,
    max_cycles_in_group: Optional[int] = None,
) -> SurplusAllocationResult:
    """
    Allocate an advance overpayment across subsequent cycles using a strict
    chronological FIFO (First-In, First-Out) waterfall.

    Why strict FIFO?
    In a Rotating Group (ROSCA), every active cycle relies on every member's
    dues to construct the full pot for that cycle's recipient. Allowing a member
    to cherry-pick future cycles (e.g. "apply to Cycle 10 but skip Cycle 4")
    creates an immediate liquidity default in Cycle 4. Therefore, advance
    credit must cascade sequentially: Cycle 4 -> Cycle 5 -> Cycle 6.

    Parameters
    ----------
    surplus_amount_ugx : int
        The extra deposit amount remaining AFTER clearing current cycle obligations,
        accumulated arrears, and unpaid late fees.
    current_cycle_number : int
        The cycle currently in progress (e.g. 3).
    standard_contribution_amount : int
        The regular per-cycle contribution required by the group (e.g. 50,000 UGX).
    cycle_specific_obligations : dict[int, int], optional
        Optional map of specific cycle numbers to customized amounts, allowing
        variable schedules (e.g. {4: 50_000, 5: 60_000}). If not provided,
        standard_contribution_amount is used for all cycles.
    max_cycles_in_group : int, optional
        Maximum cycles in this rotation round (total members). Any credit
        exceeding the final cycle sits as unallocated residual equity.

    Returns
    -------
    SurplusAllocationResult
    """
    if surplus_amount_ugx <= 0:
        return SurplusAllocationResult(
            total_surplus_ugx=0,
            cycles_fully_covered_count=0,
            fully_covered_cycles=[],
            partially_covered_cycle=None,
            unallocated_residual_ugx=0,
            next_cycle_requiring_payment=current_cycle_number + 1,
            coverage_breakdown=[],
            summary_label="No advance surplus to allocate.",
        )

    remaining_surplus = surplus_amount_ugx
    target_cycle = current_cycle_number + 1
    fully_covered = []
    partial_detail = None
    breakdown = []

    while remaining_surplus > 0:
        if max_cycles_in_group is not None and target_cycle > max_cycles_in_group:
            # Reached end of rotation; remaining credit stays in member pool
            break

        required_for_cycle = (
            cycle_specific_obligations.get(target_cycle, standard_contribution_amount)
            if cycle_specific_obligations
            else standard_contribution_amount
        )

        if remaining_surplus >= required_for_cycle:
            # Fully covers this cycle
            remaining_surplus -= required_for_cycle
            fully_covered.append(target_cycle)
            breakdown.append(
                CycleCoverageDetail(
                    cycle_number=target_cycle,
                    amount_required=required_for_cycle,
                    amount_allocated=required_for_cycle,
                    shortfall=0,
                    status=CoverageStatus.FULLY_COVERED,
                )
            )
            target_cycle += 1
        else:
            # Partially covers this cycle; exhausts remaining surplus
            allocated = remaining_surplus
            shortfall = required_for_cycle - allocated
            partial_detail = CycleCoverageDetail(
                cycle_number=target_cycle,
                amount_required=required_for_cycle,
                amount_allocated=allocated,
                shortfall=shortfall,
                status=CoverageStatus.PARTIALLY_COVERED,
            )
            breakdown.append(partial_detail)
            remaining_surplus = 0
            break

    # Determine next cycle requiring payment
    if partial_detail is not None:
        next_due_cycle = partial_detail.cycle_number
    elif fully_covered:
        next_due_cycle = fully_covered[-1] + 1
    else:
        next_due_cycle = current_cycle_number + 1

    # Human-readable summary
    if len(fully_covered) > 0 and partial_detail is not None:
        summary = (
            f"Advance covers {len(fully_covered)} full cycle(s) "
            f"(Cycles {fully_covered[0]}-{fully_covered[-1]}) + "
            f"{partial_detail.amount_allocated:,} UGX toward Cycle {partial_detail.cycle_number} "
            f"(Deficit remaining: {partial_detail.shortfall:,} UGX)."
        )
    elif len(fully_covered) > 0:
        cycles_str = (
            f"Cycle {fully_covered[0]}"
            if len(fully_covered) == 1
            else f"Cycles {fully_covered[0]}-{fully_covered[-1]}"
        )
        summary = (
            f"Advance completely clears {len(fully_covered)} future cycle(s) ({cycles_str}). "
            f"Next payment due on Cycle {next_due_cycle}."
        )
    elif partial_detail is not None:
        summary = (
            f"Advance credits {partial_detail.amount_allocated:,} UGX toward Cycle {partial_detail.cycle_number}. "
            f"Remaining deficit: {partial_detail.shortfall:,} UGX."
        )
    else:
        summary = f"{surplus_amount_ugx:,} UGX retained as general pool credit."

    return SurplusAllocationResult(
        total_surplus_ugx=surplus_amount_ugx,
        cycles_fully_covered_count=len(fully_covered),
        fully_covered_cycles=fully_covered,
        partially_covered_cycle=partial_detail,
        unallocated_residual_ugx=remaining_surplus,
        next_cycle_requiring_payment=next_due_cycle,
        coverage_breakdown=breakdown,
        summary_label=summary,
    )


# ── Branch 1B: Contribution Amount Adjustment Revaluation ──────────────────

def recalculate_credit_on_contribution_change(
    existing_credit_balance_ugx: int,
    old_contribution_amount_ugx: int,
    new_contribution_amount_ugx: int,
    current_cycle_number: int,
) -> ContributionAdjustmentResult:
    """
    Re-evaluate a member's advance credit when the group votes to change its
    contribution target (e.g. from 50,000 to 60,000 UGX).

    Design Principle:
    Microbond accounts in nominal cash (UGX), NOT synthetic cycle tokens.
    Pre-paying 100,000 UGX under a 50k regime stores 100,000 UGX of liquidity.
    If the pot target rises to 60k, that 100,000 UGX covers 1 full cycle (60k)
    and leaves 40,000 UGX for the next cycle, creating a 20,000 UGX shortfall.

    Parameters
    ----------
    existing_credit_balance_ugx : int
        Current advance balance sitting in the member's credit ledger.
    old_contribution_amount_ugx : int
        Previous cycle obligation amount.
    new_contribution_amount_ugx : int
        New voted cycle obligation amount.
    current_cycle_number : int
        The active cycle number.

    Returns
    -------
    ContributionAdjustmentResult
    """
    if new_contribution_amount_ugx <= 0:
        raise ValueError("New contribution amount must be strictly positive.")

    if existing_credit_balance_ugx <= 0:
        return ContributionAdjustmentResult(
            existing_credit_balance_ugx=0,
            old_contribution_amount_ugx=old_contribution_amount_ugx,
            new_contribution_amount_ugx=new_contribution_amount_ugx,
            new_cycles_fully_covered=0,
            partial_cycle_number=None,
            partial_cycle_credit_applied=0,
            partial_cycle_shortfall=0,
            user_advisory_message="No advance credit on file to revalue.",
        )

    full_cycles = existing_credit_balance_ugx // new_contribution_amount_ugx
    remainder = existing_credit_balance_ugx % new_contribution_amount_ugx

    partial_cycle = None
    applied_to_partial = 0
    shortfall = 0

    if remainder > 0:
        partial_cycle = current_cycle_number + full_cycles + 1
        applied_to_partial = remainder
        shortfall = new_contribution_amount_ugx - remainder

    # Compose UX advisory message
    if full_cycles > 0 and partial_cycle is not None:
        msg = (
            f"The group contribution changed from {old_contribution_amount_ugx:,} UGX "
            f"to {new_contribution_amount_ugx:,} UGX. Your advance credit of {existing_credit_balance_ugx:,} UGX "
            f"now fully covers {full_cycles} cycle(s), with {applied_to_partial:,} UGX applied "
            f"toward Cycle {partial_cycle}. You will have a small top-up of {shortfall:,} UGX due for Cycle {partial_cycle}."
        )
    elif full_cycles > 0:
        msg = (
            f"The group contribution changed to {new_contribution_amount_ugx:,} UGX. "
            f"Your credit of {existing_credit_balance_ugx:,} UGX perfectly covers {full_cycles} full cycle(s)."
        )
    else:
        msg = (
            f"The group contribution changed to {new_contribution_amount_ugx:,} UGX. "
            f"Your advance credit of {existing_credit_balance_ugx:,} UGX is applied to Cycle {current_cycle_number + 1}. "
            f"Remaining balance due: {shortfall:,} UGX."
        )

    return ContributionAdjustmentResult(
        existing_credit_balance_ugx=existing_credit_balance_ugx,
        old_contribution_amount_ugx=old_contribution_amount_ugx,
        new_contribution_amount_ugx=new_contribution_amount_ugx,
        new_cycles_fully_covered=full_cycles,
        partial_cycle_number=partial_cycle,
        partial_cycle_credit_applied=applied_to_partial,
        partial_cycle_shortfall=shortfall,
        user_advisory_message=msg,
    )


# ── Branch 2C & 2D: Privacy Broadcast & Queue Invariance ───────────────────

def format_deposit_broadcast_message(
    member_display_name: str,
    entered_amount_ugx: int,
    cycle_number: int,
    cycle_obligation_ugx: int,
    is_advance: bool = False,
) -> Dict[str, str]:
    """
    Generate broadcast announcements balancing social accountability and privacy.

    Branch 2C Rule:
    The group chat announces that the member fulfilled their obligation for the
    current cycle. It DOES NOT broadcast surplus advance figures (e.g. 100k extra
    covering 2 cycles ahead). Revealing liquidity cushions exposes members to
    coercive peer-to-peer borrowing or resentment in local community groups.

    Branch 2D Rule:
    Payout queue standing is 100% invariant to advance deposits. Payout order
    is locked to `payout_position` and cannot be bought or jumped.

    Returns
    -------
    dict with 'group_chat_broadcast' (public) and 'member_private_receipt' (private).
    """
    # Public announcement: Confirms payment for current cycle without flaunting excess cash
    public_msg = f"🎉 {member_display_name} contributed for Cycle {cycle_number}."

    # Private receipt for the member's eyes only
    if is_advance and entered_amount_ugx > cycle_obligation_ugx:
        surplus = entered_amount_ugx - cycle_obligation_ugx
        private_msg = (
            f"Deposit Confirmed: {entered_amount_ugx:,} UGX received. "
            f"Cycle {cycle_number} is cleared. Surplus of {surplus:,} UGX has been "
            f"credited forward to upcoming cycles. Your payout turn position remains unchanged."
        )
    else:
        private_msg = (
            f"Deposit Confirmed: {entered_amount_ugx:,} UGX received. "
            f"Cycle {cycle_number} is fully settled."
        )

    return {
        "group_chat_broadcast": public_msg,
        "member_private_receipt": private_msg,
    }


# ── Branch 3E & 3F: Accidental Overpayment Refund Safeguards ─────────────────

def validate_surplus_withdrawal(
    member_credit_balance_ugx: int,
    requested_withdrawal_ugx: int,
    group_pool_liquid_balance_ugx: int,
    upcoming_cycle_payout_amount_ugx: int,
    hours_since_deposit: float,
    signer_approvals_count: int,
    required_signer_approvals: int = 1,
    cooldown_timelock_hours: float = 2.0,
    momo_disbursement_fee_ugx: int = 1000,
    min_liquidity_reserve_pct: float = 0.05,
) -> SurplusWithdrawalEvaluation:
    """
    Validate and guard a member's request to withdraw an accidental overpayment.

    Security & Anti-Abuse Rules:
    1. Equity Bound: A member can ONLY withdraw unallocated advance credit.
       Current-cycle contributions and settled historical rounds are committed
       and strictly non-withdrawable.
    2. Liquidity Buffer: A group's liquid cash AFTER the refund must be at least:
       `upcoming_cycle_payout_amount_ugx + (total_pool * reserve_pct)`.
       An advance refund request can NEVER be allowed to cause the scheduled
       round recipient's payout to bounce.
    3. Multi-Sig Approval: Accidental refund requires admin/treasurer authorization.
    4. Anti-Transit Timelock: A 2-hour cooldown stops deposit-wash exploit loops.
    5. Telecom Fee Neutrality: Outgoing MoMo disbursement fee is netted from the
       disbursement so the group pool and platform incur 0 UGX loss.

    Parameters
    ----------
    member_credit_balance_ugx : int
        The member's verified unallocated advance credit (e.g. 450,000 UGX).
    requested_withdrawal_ugx : int
        Amount requested for refund to mobile money.
    group_pool_liquid_balance_ugx : int
        Current liquid cash in the group's MTN escrow collection wallet.
    upcoming_cycle_payout_amount_ugx : int
        The pot amount committed to the recipient of the active cycle.
    hours_since_deposit : float
        Elapsed hours since the overpayment deposit confirmed.
    signer_approvals_count : int
        Count of verified multi-sig approvals logged by admins/treasurers.
    required_signer_approvals : int
        Threshold of approvals needed (default 1 admin/treasurer).
    cooldown_timelock_hours : float
        Minimum waiting period (default 2.0 hours).
    momo_disbursement_fee_ugx : int
        Network cost to disburse B2C mobile money (default 1,000 UGX).
    min_liquidity_reserve_pct : float
        Safety margin of pool retained (default 5%).

    Returns
    -------
    SurplusWithdrawalEvaluation
    """
    # ── Gate 0: Basic bounds check ─────────────────────────────────────────
    if requested_withdrawal_ugx <= momo_disbursement_fee_ugx:
        return SurplusWithdrawalEvaluation(
            status=WithdrawalEligibilityStatus.BELOW_MINIMUM_THRESHOLD,
            is_eligible=False,
            requested_amount_ugx=requested_withdrawal_ugx,
            approved_gross_amount_ugx=0,
            telecom_disbursement_fee_ugx=momo_disbursement_fee_ugx,
            net_payout_to_member_ugx=0,
            remaining_credit_after_refund=member_credit_balance_ugx,
            group_pool_balance_after_refund=group_pool_liquid_balance_ugx,
            reason_message=(
                f"Requested withdrawal ({requested_withdrawal_ugx:,} UGX) must exceed "
                f"the network transfer fee of {momo_disbursement_fee_ugx:,} UGX."
            ),
        )

    # ── Gate 1: Member credit bound check ──────────────────────────────────
    if requested_withdrawal_ugx > member_credit_balance_ugx:
        return SurplusWithdrawalEvaluation(
            status=WithdrawalEligibilityStatus.EXCEEDS_CREDIT_BALANCE,
            is_eligible=False,
            requested_amount_ugx=requested_withdrawal_ugx,
            approved_gross_amount_ugx=0,
            telecom_disbursement_fee_ugx=momo_disbursement_fee_ugx,
            net_payout_to_member_ugx=0,
            remaining_credit_after_refund=member_credit_balance_ugx,
            group_pool_balance_after_refund=group_pool_liquid_balance_ugx,
            reason_message=(
                f"Cannot withdraw {requested_withdrawal_ugx:,} UGX. "
                f"Your unallocated advance credit is only {member_credit_balance_ugx:,} UGX. "
                f"(Current cycle dues are committed to the round pot and cannot be refunded)."
            ),
        )

    # ── Gate 2: Group pool liquidity preservation check ───────────────────
    min_required_pool = upcoming_cycle_payout_amount_ugx + int(
        group_pool_liquid_balance_ugx * min_liquidity_reserve_pct
    )
    pool_after_withdrawal = group_pool_liquid_balance_ugx - requested_withdrawal_ugx

    if pool_after_withdrawal < min_required_pool:
        return SurplusWithdrawalEvaluation(
            status=WithdrawalEligibilityStatus.INSUFFICIENT_POOL_CASH,
            is_eligible=False,
            requested_amount_ugx=requested_withdrawal_ugx,
            approved_gross_amount_ugx=0,
            telecom_disbursement_fee_ugx=momo_disbursement_fee_ugx,
            net_payout_to_member_ugx=0,
            remaining_credit_after_refund=member_credit_balance_ugx,
            group_pool_balance_after_refund=group_pool_liquid_balance_ugx,
            reason_message=(
                f"Withdrawal temporarily restricted: processing this refund would leave "
                f"the group pool with {pool_after_withdrawal:,} UGX, which is below the "
                f"{min_required_pool:,} UGX needed to guarantee the scheduled round payout. "
                f"Wait until the current round payout clears or contact the Group Treasurer."
            ),
        )

    # ── Gate 3: Cooldown timelock verification ────────────────────────────
    if hours_since_deposit < cooldown_timelock_hours:
        remaining_wait = round(cooldown_timelock_hours - hours_since_deposit, 1)
        return SurplusWithdrawalEvaluation(
            status=WithdrawalEligibilityStatus.TIMELOCK_ACTIVE,
            is_eligible=False,
            requested_amount_ugx=requested_withdrawal_ugx,
            approved_gross_amount_ugx=0,
            telecom_disbursement_fee_ugx=momo_disbursement_fee_ugx,
            net_payout_to_member_ugx=0,
            remaining_credit_after_refund=member_credit_balance_ugx,
            group_pool_balance_after_refund=group_pool_liquid_balance_ugx,
            reason_message=(
                f"Security timelock active: please allow {remaining_wait} more hour(s) "
                f"before initiating a reversal. This prevents duplicate mobile money processing."
            ),
        )

    # ── Gate 4: Multi-sig governance approval check ────────────────────────
    if signer_approvals_count < required_signer_approvals:
        return SurplusWithdrawalEvaluation(
            status=WithdrawalEligibilityStatus.PENDING_APPROVALS,
            is_eligible=False,
            requested_amount_ugx=requested_withdrawal_ugx,
            approved_gross_amount_ugx=0,
            telecom_disbursement_fee_ugx=momo_disbursement_fee_ugx,
            net_payout_to_member_ugx=0,
            remaining_credit_after_refund=member_credit_balance_ugx,
            group_pool_balance_after_refund=group_pool_liquid_balance_ugx,
            reason_message=(
                f"Refund request is pending approval from the Group Treasurer or Admin "
                f"({signer_approvals_count}/{required_signer_approvals} approvals logged)."
            ),
        )

    # ── All Gates Passed: Authorize disbursement ───────────────────────────
    net_payout = requested_withdrawal_ugx - momo_disbursement_fee_ugx
    remaining_credit = member_credit_balance_ugx - requested_withdrawal_ugx

    return SurplusWithdrawalEvaluation(
        status=WithdrawalEligibilityStatus.ELIGIBLE,
        is_eligible=True,
        requested_amount_ugx=requested_withdrawal_ugx,
        approved_gross_amount_ugx=requested_withdrawal_ugx,
        telecom_disbursement_fee_ugx=momo_disbursement_fee_ugx,
        net_payout_to_member_ugx=net_payout,
        remaining_credit_after_refund=remaining_credit,
        group_pool_balance_after_refund=pool_after_withdrawal,
        reason_message=(
            f"Withdrawal approved. {net_payout:,} UGX will be sent to your registered "
            f"Mobile Money number ({requested_withdrawal_ugx:,} UGX refund minus "
            f"{momo_disbursement_fee_ugx:,} UGX network transfer fee). "
            f"Remaining advance credit: {remaining_credit:,} UGX."
        ),
    )
