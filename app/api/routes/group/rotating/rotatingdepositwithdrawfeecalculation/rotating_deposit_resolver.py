"""
rotating_deposit_resolver.py
─────────────────────────────────────────────────────────────────────────────
Rotating Group (MERRY_GO_ROUND / ROSCA) — Deposit Resolution Engine

WHAT THIS MODULE SOLVES:
  When a member opens the app to make a deposit, the system must answer
  three questions BEFORE touching mobile money:

    1. WHAT DO YOU OWE?
       Has the member missed previous cycles? Do they have unpaid late
       fee penalties? Have they already partially paid this cycle?
       → Total outstanding = arrears + penalties - already_paid

    2. IS YOUR AMOUNT VALID?
       Does the group allow partial payments? Can they overpay/prepay?
       Does their entered amount satisfy the minimum required?
       → Returns clear rejection messages or APPROVED status.

    3. HOW MUCH DO I CHARGE MTN?
       Combines the validated deposit amount with the psychological fee
       engine + the milestone-based amortized payout fee.
       → Returns the final charge_amount to send to MTN RequestToPay.

THE THREE DEPOSIT STATES:
  ┌─────────────────────────────────────────────────────────────────┐
  │ MISSED PAYMENT (Arrears)                                        │
  │   Member didn't pay cycle 3. Now in cycle 4.                   │
  │   → amount_owed includes cycle 3 arrears + any late fee.       │
  │   → If allow_partial=False → must pay everything at once.      │
  │   → If allow_partial=True  → can pay any amount ≥ 1 UGX.      │
  │                                                                 │
  │ ADVANCE PAYMENT (Overpay)                                       │
  │   Member wants to pay 3 cycles ahead (e.g. 100,000 UGX         │
  │   when 10,000 UGX is due today).                               │
  │   → If allow_advance=True  → accepted. Surplus credits forward.│
  │   → If allow_advance=False → blocked. Must pay exact amount.   │
  │                                                                 │
  │ EXACT / NORMAL PAYMENT                                          │
  │   Member pays exactly what is due. No edge cases.              │
  │   → Always accepted.                                           │
  └─────────────────────────────────────────────────────────────────┘

GRACE PERIOD LOGIC:
  The group may define a grace window (e.g. 24h) after the due date.
  During grace: obligation status stays "PENDING" — no late fee yet.
  After grace:  obligation status flips to "LATE" and a GroupPenalty
                row is (or should be) written by the cron job.
  This resolver reads the ALREADY-WRITTEN penalty rows from the DB
  (GroupPenalty.is_paid == False) to calculate the penalty total.
  It does NOT create new penalties — that is the cron job's job.

USAGE (from deposit_pipeline.py):
  from app.api.routes.group.rotating.rotatingdepositwithdrawfeecalculation.rotating_deposit_resolver import (
      resolve_deposit_intent,
      DepositResolution,
      DepositStatus,
  )

  resolution = resolve_deposit_intent(
      entered_amount         = payload.entered_amount,
      contribution_amount    = int(rot.contribution_amount),
      amount_paid_this_cycle = obligation.amount_paid if obligation else 0,
      accumulated_arrears    = arrears_total,        # sum of unpaid prior obligations
      unpaid_penalties_ugx   = penalties_total,      # sum of GroupPenalty.penalty_amount
      milestone_round_number = stored_milestone_round,
      current_round_number   = rot.current_cycle,
      allow_partial          = rot.allow_partial_payments,
      allow_advance          = rot.allow_advance_deposits,
  )

  if resolution.status == DepositStatus.REJECTED:
      raise HTTPException(400, detail=resolution.rejection_reason)

  # Send resolution.final_charge_amount to MTN RequestToPay
─────────────────────────────────────────────────────────────────────────────
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.core.fee_engine import calculate_deposit_fee, DepositFeeBreakdown
from app.api.routes.group.rotating.rotatingdepositwithdrawfeecalculation.payout_fee_milestone_amortizer import (
    get_charge_for_deposit,
    TARGET_PAYOUT_FEE,
)


# ── Enums ──────────────────────────────────────────────────────────────────

class DepositStatus(str, Enum):
    """Outcome of the deposit resolution check."""
    APPROVED        = "APPROVED"        # Amount is valid — proceed to MTN
    REJECTED        = "REJECTED"        # Amount violates group rules — show error
    APPROVED_PARTIAL= "APPROVED_PARTIAL"# Partial payment accepted (underpayment OK)
    APPROVED_ADVANCE= "APPROVED_ADVANCE"# Overpayment accepted (credited forward)


class PaymentType(str, Enum):
    """What kind of payment this deposit represents."""
    NORMAL          = "NORMAL"          # Exact or within normal range
    ARREARS         = "ARREARS"         # Catching up missed past cycles
    PARTIAL         = "PARTIAL"         # Paying less than total due (allowed)
    ADVANCE         = "ADVANCE"         # Paying more than total due (allowed)
    ARREARS_PARTIAL = "ARREARS_PARTIAL" # Catching up but still not fully cleared


# ── Data Models ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DepositBreakdown:
    """
    Detailed line-by-line breakdown of what the member owes and what
    they are paying. Returned as part of DepositResolution for UI display.

    All amounts are in whole UGX (int).
    """
    # What the member owes
    current_cycle_due: int          # Base contribution for this cycle
    amount_already_paid: int        # What they already deposited this cycle
    current_cycle_remaining: int    # current_cycle_due - amount_already_paid
    arrears_owed: int               # Sum of unpaid prior cycle obligations
    penalties_owed: int             # Sum of unpaid GroupPenalty rows
    total_outstanding: int          # current_remaining + arrears + penalties

    # What the member is paying
    entered_amount: int             # Raw amount the user typed
    amount_to_credit: int           # Net amount credited to the savings pool
    surplus_credited_forward: int   # Any overpayment credited to next cycle
    shortfall_remaining: int        # If partial: how much still outstanding after

    # Fee components
    mtn_collection_fee: int         # MTN's 1.5% cut
    microbond_base_fee: int         # Microbond's psychological base fee
    milestone_payout_fee: int       # Hidden payout amortization (0 or 979)
    total_fee: int                  # All fees combined
    final_charge_amount: int        # What lands on the MTN MoMo PIN prompt

    is_milestone_deposit: bool      # True if hidden payout fee is applied


@dataclass(frozen=True)
class DepositResolution:
    """
    The complete, authoritative result of resolving a deposit intent.
    The deposit_pipeline.py endpoint reads this object to:
      - Accept or reject the request
      - Pass final_charge_amount to MTN RequestToPay
      - Update MemberObligation and GroupPenalty rows post-confirmation

    Attributes
    ----------
    status : DepositStatus
        APPROVED, REJECTED, APPROVED_PARTIAL, or APPROVED_ADVANCE.
    payment_type : PaymentType
        Classification for audit logs and UI labels.
    rejection_reason : str | None
        Human-readable explanation shown to the user on rejection. None if approved.
    breakdown : DepositBreakdown | None
        Full line-by-line breakdown. None if rejected.
    final_charge_amount : int
        The exact UGX figure to pass to MTN RequestToPay. 0 if rejected.
    display_summary : str
        One-line human-readable confirmation for the mobile UI, e.g.:
        "You will be charged 51,482 UGX. This covers your 50,000 UGX
         contribution + 1,482 UGX processing fee."
    """
    status: DepositStatus
    payment_type: PaymentType
    rejection_reason: Optional[str]
    breakdown: Optional[DepositBreakdown]
    final_charge_amount: int
    display_summary: str

    @property
    def is_approved(self) -> bool:
        return self.status != DepositStatus.REJECTED

    def to_dict(self) -> dict:
        """JSON-serializable for the deposit-quote API response."""
        result = {
            "status": self.status.value,
            "payment_type": self.payment_type.value,
            "rejection_reason": self.rejection_reason,
            "final_charge_amount": self.final_charge_amount,
            "display_summary": self.display_summary,
        }
        if self.breakdown:
            result["breakdown"] = {
                "current_cycle_due": self.breakdown.current_cycle_due,
                "amount_already_paid": self.breakdown.amount_already_paid,
                "current_cycle_remaining": self.breakdown.current_cycle_remaining,
                "arrears_owed": self.breakdown.arrears_owed,
                "penalties_owed": self.breakdown.penalties_owed,
                "total_outstanding": self.breakdown.total_outstanding,
                "entered_amount": self.breakdown.entered_amount,
                "amount_to_credit": self.breakdown.amount_to_credit,
                "surplus_credited_forward": self.breakdown.surplus_credited_forward,
                "shortfall_remaining": self.breakdown.shortfall_remaining,
                "mtn_collection_fee": self.breakdown.mtn_collection_fee,
                "microbond_base_fee": self.breakdown.microbond_base_fee,
                "milestone_payout_fee": self.breakdown.milestone_payout_fee,
                "total_fee": self.breakdown.total_fee,
                "final_charge_amount": self.breakdown.final_charge_amount,
                "is_milestone_deposit": self.breakdown.is_milestone_deposit,
            }
        return result


# ── Internal Helpers ───────────────────────────────────────────────────────

def _build_rejection(reason: str) -> DepositResolution:
    return DepositResolution(
        status=DepositStatus.REJECTED,
        payment_type=PaymentType.NORMAL,
        rejection_reason=reason,
        breakdown=None,
        final_charge_amount=0,
        display_summary=reason,
    )


def _classify_payment(
    entered: int,
    total_outstanding: int,
    has_arrears: bool,
    is_partial: bool,
    is_advance: bool,
) -> PaymentType:
    if has_arrears and entered < total_outstanding:
        return PaymentType.ARREARS_PARTIAL
    if has_arrears:
        return PaymentType.ARREARS
    if is_partial:
        return PaymentType.PARTIAL
    if is_advance:
        return PaymentType.ADVANCE
    return PaymentType.NORMAL


# ── Public API ─────────────────────────────────────────────────────────────

def resolve_deposit_intent(
    entered_amount: int,
    contribution_amount: int,
    amount_paid_this_cycle: int,
    accumulated_arrears: int,
    unpaid_penalties_ugx: int,
    milestone_round_number: int,
    current_round_number: int,
    allow_partial: bool,
    allow_advance: bool,
) -> DepositResolution:
    """
    Resolve a member's deposit intent for a Rotating Group (MERRY_GO_ROUND).

    This is the single authoritative function that decides whether a deposit
    is valid, what it covers, and what charge to send to MTN RequestToPay.

    Parameters
    ----------
    entered_amount : int
        The raw UGX amount the member typed into the deposit screen.
    contribution_amount : int
        The fixed per-cycle contribution required by the group (from RotatingGroupDetails).
    amount_paid_this_cycle : int
        How much the member has already deposited toward the CURRENT cycle
        (from MemberObligation.amount_paid).
    accumulated_arrears : int
        Total UGX owed from PREVIOUS unpaid cycles
        (sum of MemberObligation.amount_due - amount_paid for all prior cycles
        where status != 'PAID'). Pass 0 if none.
    unpaid_penalties_ugx : int
        Total UGX in uncleared late fee penalties
        (sum of GroupPenalty.penalty_amount where is_paid=False). Pass 0 if none.
    milestone_round_number : int
        Pre-stored milestone round for this member (from DB).
        Used to determine if this deposit carries the hidden payout fee.
    current_round_number : int
        The cycle/round number being deposited into right now.
    allow_partial : bool
        Whether the group permits deposits below the required amount
        (from RotatingGroupDetails.allow_partial_payments).
    allow_advance : bool
        Whether the group permits deposits above the required amount
        (from RotatingGroupDetails.allow_advance_deposits).

    Returns
    -------
    DepositResolution
        Full resolution result. Check .is_approved before proceeding.
        If approved, pass .final_charge_amount to MTN RequestToPay.

    Examples
    --------
    # Normal on-time payment
    >>> r = resolve_deposit_intent(
    ...     entered_amount=100_000, contribution_amount=100_000,
    ...     amount_paid_this_cycle=0, accumulated_arrears=0,
    ...     unpaid_penalties_ugx=0, milestone_round_number=5,
    ...     current_round_number=3, allow_partial=False, allow_advance=False,
    ... )
    >>> r.status
    <DepositStatus.APPROVED: 'APPROVED'>
    >>> r.final_charge_amount  # 102,981 (standard psychological fee)
    102981

    # Missed last cycle, back to pay arrears too
    >>> r = resolve_deposit_intent(
    ...     entered_amount=200_000, contribution_amount=100_000,
    ...     amount_paid_this_cycle=0, accumulated_arrears=100_000,
    ...     unpaid_penalties_ugx=10_000, milestone_round_number=5,
    ...     current_round_number=3, allow_partial=True, allow_advance=True,
    ... )
    >>> r.payment_type
    <PaymentType.ARREARS: 'ARREARS'>
    >>> r.breakdown.total_outstanding
    210000

    # Blocked: partial not allowed, tries to underpay
    >>> r = resolve_deposit_intent(
    ...     entered_amount=50_000, contribution_amount=100_000,
    ...     amount_paid_this_cycle=0, accumulated_arrears=0,
    ...     unpaid_penalties_ugx=0, milestone_round_number=5,
    ...     current_round_number=3, allow_partial=False, allow_advance=True,
    ... )
    >>> r.status
    <DepositStatus.REJECTED: 'REJECTED'>
    """
    # ── Guard: entered amount must be positive ─────────────────────────────
    if entered_amount <= 0:
        return _build_rejection("Deposit amount must be greater than 0 UGX.")

    # ── Step 1: Calculate total outstanding ───────────────────────────────
    current_remaining = max(0, contribution_amount - amount_paid_this_cycle)
    total_outstanding = current_remaining + accumulated_arrears + unpaid_penalties_ugx
    has_arrears = accumulated_arrears > 0 or unpaid_penalties_ugx > 0

    # ── Step 2: Validate against group rules ──────────────────────────────
    is_underpayment = total_outstanding > 0 and entered_amount < total_outstanding
    is_overpayment  = total_outstanding > 0 and entered_amount > total_outstanding

    # Partial payment check: if group disallows partial, member must clear full outstanding
    if is_underpayment and not allow_partial:
        outstanding_fmt = f"{total_outstanding:,}"
        detail = (
            f"Partial payments are not allowed in this group. "
            f"Please deposit the full outstanding amount of {outstanding_fmt} UGX."
        )
        if has_arrears:
            detail += (
                f" This includes {accumulated_arrears:,} UGX in arrears"
                f" and {unpaid_penalties_ugx:,} UGX in late fees."
            )
        return _build_rejection(detail)

    # Advance payment check: if group disallows overpay, member must pay exactly what's due
    if is_overpayment and not allow_advance and total_outstanding > 0:
        return _build_rejection(
            f"Advance payments are not allowed in this group. "
            f"Please deposit exactly {total_outstanding:,} UGX."
        )

    # ── Step 3: Determine what this deposit actually credits ──────────────
    # The amount credited to the savings pool is the entered amount (pre-fees).
    # Any surplus beyond total_outstanding is credited forward to the next cycle.
    amount_to_credit     = entered_amount
    surplus_forward      = max(0, entered_amount - total_outstanding) if total_outstanding > 0 else 0
    shortfall_remaining  = max(0, total_outstanding - entered_amount)

    # ── Step 4: Calculate the MTN charge via the fee engine ───────────────
    # The fee is calculated on the entered_amount (savings portion only).
    # Use get_charge_for_deposit to automatically include the milestone payout
    # fee if this round is the member's assigned hidden fee round.
    final_charge_amount = get_charge_for_deposit(
        group_target_amount=entered_amount,
        member_milestone_round=milestone_round_number,
        current_round_number=current_round_number,
    )

    # Pull individual fee components for the breakdown display
    base: DepositFeeBreakdown = calculate_deposit_fee(entered_amount)
    is_milestone = (current_round_number == milestone_round_number)
    milestone_fee = TARGET_PAYOUT_FEE if is_milestone else 0
    total_fee = (final_charge_amount - entered_amount)

    # ── Step 5: Classify the payment type ─────────────────────────────────
    payment_type = _classify_payment(
        entered=entered_amount,
        total_outstanding=total_outstanding,
        has_arrears=has_arrears,
        is_partial=is_underpayment,
        is_advance=is_overpayment,
    )

    # ── Step 6: Determine status ───────────────────────────────────────────
    if is_underpayment:
        deposit_status = DepositStatus.APPROVED_PARTIAL
    elif is_overpayment:
        deposit_status = DepositStatus.APPROVED_ADVANCE
    else:
        deposit_status = DepositStatus.APPROVED

    # ── Step 7: Build the human-readable summary ───────────────────────────
    summary_parts = [
        f"You will be charged {final_charge_amount:,} UGX.",
        f"This covers your {entered_amount:,} UGX contribution",
        f"+ {total_fee:,} UGX processing fee.",
    ]
    if is_milestone:
        summary_parts.append("(Includes a one-time network recovery charge.)")
    if surplus_forward > 0:
        summary_parts.append(
            f"{surplus_forward:,} UGX will be credited toward your next cycle."
        )
    if shortfall_remaining > 0:
        summary_parts.append(
            f"You still owe {shortfall_remaining:,} UGX after this deposit."
        )
    if has_arrears:
        summary_parts.append(
            f"Includes {accumulated_arrears:,} UGX arrears + {unpaid_penalties_ugx:,} UGX late fees."
        )

    # ── Step 8: Build and return the full resolution ───────────────────────
    breakdown = DepositBreakdown(
        current_cycle_due=contribution_amount,
        amount_already_paid=amount_paid_this_cycle,
        current_cycle_remaining=current_remaining,
        arrears_owed=accumulated_arrears,
        penalties_owed=unpaid_penalties_ugx,
        total_outstanding=total_outstanding,
        entered_amount=entered_amount,
        amount_to_credit=amount_to_credit,
        surplus_credited_forward=surplus_forward,
        shortfall_remaining=shortfall_remaining,
        mtn_collection_fee=base.mtn_fee,
        microbond_base_fee=base.platform_fee,
        milestone_payout_fee=milestone_fee,
        total_fee=total_fee,
        final_charge_amount=final_charge_amount,
        is_milestone_deposit=is_milestone,
    )

    return DepositResolution(
        status=deposit_status,
        payment_type=payment_type,
        rejection_reason=None,
        breakdown=breakdown,
        final_charge_amount=final_charge_amount,
        display_summary=" ".join(summary_parts),
    )
