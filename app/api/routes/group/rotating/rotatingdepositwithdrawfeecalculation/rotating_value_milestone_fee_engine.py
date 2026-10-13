"""
rotating_value_milestone_fee_engine.py
─────────────────────────────────────────────────────────────────────────────
Rotating Group — Flexible Value-Threshold Payout Fee Engine

WHY THIS REPLACES THE ROUND-NUMBER MILESTONE:
  The original payout_fee_milestone_amortizer.py assigned the hidden 979 UGX
  fee to a specific round number (e.g. "Round 5"). This breaks the moment
  a user pays anything other than one exact deposit per round:

    • Advance payer deposits 100,000 UGX on Day 1 (10 rounds worth at once)
      → "Round 5" never happens as a separate event → fee is never collected.

    • Late payer misses 3 rounds, catches up with a single 30,000 UGX deposit
      → They skip Rounds 1-3 in one payment → milestone round may be bypassed.

  This module fixes the problem by tying the fee trigger to a CUMULATIVE
  VALUE THRESHOLD — the same approach used by the Target group engine.

STRATEGY: Cumulative Value Milestone
  At group creation, each member is assigned a UGX threshold derived from
  a random percentage (20%, 50%, or 80%) of their total cycle commitment.

  Example: 10-round cycle, 100,000 UGX per round → total = 1,000,000 UGX
    • EARLY   (20%) → threshold = 200,000 UGX
    • MID     (50%) → threshold = 500,000 UGX
    • LATE    (80%) → threshold = 800,000 UGX

  The 979 UGX fee fires on the FIRST deposit that pushes their cumulative
  total past their assigned threshold — regardless of how many transactions
  it took to get there and regardless of calendar timing.

  This guarantees:
    ✓ Standard daily payer:  hits threshold on their assigned day naturally.
    ✓ Advance lump-sum payer: threshold crossed on first big deposit.
    ✓ Late catch-up payer:   threshold crossed on their combined catch-up.
    ✓ Zero double-charging:  fee_already_collected flag prevents repeat.

USAGE:
  # Step 1: At group creation — assign each member their threshold (store in DB)
  from app.api.routes.group.rotating.rotatingdepositwithdrawfeecalculation.rotating_value_milestone_fee_engine import (
      assign_member_value_milestone,
  )
  threshold = assign_member_value_milestone(
      contribution_amount=100_000,
      total_rounds=10,
  )
  # e.g. 500_000 → store as GroupMembership.fee_milestone_value_ugx

  # Step 2: On every deposit — calculate exact charge
  from app.api.routes.group.rotating.rotatingdepositwithdrawfeecalculation.rotating_value_milestone_fee_engine import (
      calculate_flexible_rotate_deposit,
  )
  result = calculate_flexible_rotate_deposit(
      deposit_amount          = payload.entered_amount,
      current_saved_amount    = membership.total_contributed,
      assigned_value_milestone= membership.fee_milestone_value_ugx,
      fee_already_collected   = membership.payout_fee_collected,
  )
  # Pass result.final_charge_amount to MTN RequestToPay.
  # If result.milestone_triggered_now → flip payout_fee_collected=True in DB.
─────────────────────────────────────────────────────────────────────────────
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np

from app.core.fee_engine import calculate_deposit_fee, DepositFeeBreakdown


# ── Constants ──────────────────────────────────────────────────────────────

MTN_FLAT_PAYOUT_FEE: int = 300      # UGX — MTN disbursement cost
MICROBOND_PAYOUT_PROFIT: int = 679  # UGX — Microbond margin per payout
TARGET_PAYOUT_FEE: int = MTN_FLAT_PAYOUT_FEE + MICROBOND_PAYOUT_PROFIT  # 979

# Percentage points of total cycle commitment at which the fee may trigger.
# Three brackets keep the distribution unpredictable across members.
MILESTONE_PERCENTAGES: list[float] = [0.20, 0.50, 0.80]

MILESTONE_LABEL: dict[float, str] = {
    0.20: "EARLY_20PCT",
    0.50: "MID_50PCT",
    0.80: "LATE_80PCT",
}


# ── Data Model ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FlexibleRotateDepositResult:
    """
    Result of a single flexible deposit calculation for a Rotating Group.

    Attributes
    ----------
    deposit_amount : int
        The raw UGX the member is depositing right now.
    base_charge_amount : int
        Standard charge before payout fee (deposit + MTN 1.5% + Microbond base).
    mtn_deposit_fee : int
        MTN's 1.5% collection fee.
    microbond_base_fee : int
        Microbond psychological base platform fee.
    hidden_payout_fee : int
        979 UGX if milestone triggered, 0 otherwise.
    final_charge_amount : int
        Exact UGX sent to MTN RequestToPay (on the member's MoMo PIN prompt).
    milestone_triggered_now : bool
        True if this deposit crossed the value threshold and triggered the fee.
        If True → flip membership.payout_fee_collected = True in the DB.
    new_cumulative_total : int
        The member's total_contributed after this deposit lands (for DB update).
    assigned_value_milestone : int
        Echo of the threshold used (for audit logging).
    """
    deposit_amount: int
    base_charge_amount: int
    mtn_deposit_fee: int
    microbond_base_fee: int
    hidden_payout_fee: int
    final_charge_amount: int
    milestone_triggered_now: bool
    new_cumulative_total: int
    assigned_value_milestone: int

    def to_dict(self) -> dict:
        return {
            "deposit_amount": self.deposit_amount,
            "base_charge_amount": self.base_charge_amount,
            "mtn_deposit_fee": self.mtn_deposit_fee,
            "microbond_base_fee": self.microbond_base_fee,
            "hidden_payout_fee": self.hidden_payout_fee,
            "final_charge_amount": self.final_charge_amount,
            "milestone_triggered_now": self.milestone_triggered_now,
            "new_cumulative_total": self.new_cumulative_total,
        }


# ── Public API ─────────────────────────────────────────────────────────────

def assign_member_value_milestone(
    contribution_amount: int,
    total_rounds: int,
    random_seed: Optional[int] = None,
) -> int:
    """
    Assign a UGX value threshold to a member at group creation.
    Store the result in the DB as `GroupMembership.fee_milestone_value_ugx`.

    The threshold is a random percentage (20%, 50%, or 80%) of the member's
    total expected cycle contribution.

    Parameters
    ----------
    contribution_amount : int
        The per-deposit target (e.g. 100,000 UGX per round).
    total_rounds : int
        Total number of rounds in the cycle (e.g. 10 members = 10 rounds).
    random_seed : int, optional
        Fix numpy seed for reproducible tests.

    Returns
    -------
    int
        The UGX threshold value. The 979 UGX fee fires when the member's
        cumulative savings crosses this amount.

    Example
    -------
    >>> assign_member_value_milestone(100_000, 10)
    500000   # 50% of 1,000,000 → fee fires when they've paid 500k total
    """
    rng = np.random.default_rng(random_seed)
    pct = float(rng.choice(MILESTONE_PERCENTAGES))
    total_cycle_commitment = contribution_amount * total_rounds
    return int(total_cycle_commitment * pct)


def calculate_flexible_rotate_deposit(
    deposit_amount: int,
    current_saved_amount: int,
    assigned_value_milestone: int,
    fee_already_collected: bool,
) -> FlexibleRotateDepositResult:
    """
    Calculate the exact MTN RequestToPay charge for a rotating group deposit,
    supporting lump-sum advance payments and catch-up arrears payments.

    The hidden 979 UGX payout fee fires on the first deposit that pushes the
    member's cumulative total past their assigned UGX value threshold —
    regardless of how many transactions it took to get there.

    Parameters
    ----------
    deposit_amount : int
        The UGX amount being deposited right now (can be exact, catch-up,
        or lump-sum advance — any positive amount).
    current_saved_amount : int
        The member's total_contributed BEFORE this deposit (from DB).
        This is the running cumulative ledger total.
    assigned_value_milestone : int
        The pre-stored UGX threshold assigned at group creation
        (from GroupMembership.fee_milestone_value_ugx).
    fee_already_collected : bool
        True if the hidden 979 UGX fee was already collected from this
        member in a prior deposit this cycle.

    Returns
    -------
    FlexibleRotateDepositResult
        Contains final_charge_amount for MTN + milestone_triggered_now flag.

    Raises
    ------
    ValueError
        If deposit_amount or assigned_value_milestone is not a positive int.

    Examples
    --------
    # Standard daily payer — 10,000/day, milestone at 50,000
    >>> r = calculate_flexible_rotate_deposit(10_000, 40_000, 50_000, False)
    >>> r.milestone_triggered_now   # 40k+10k=50k hits threshold
    True
    >>> r.hidden_payout_fee
    979

    # Advance payer — pays 100,000 on Day 1, milestone at 50,000
    >>> r = calculate_flexible_rotate_deposit(100_000, 0, 50_000, False)
    >>> r.milestone_triggered_now   # 0+100k > 50k, triggers immediately
    True

    # Catch-up payer — missed 3 days, pays 30,000 lump, milestone at 25,000
    >>> r = calculate_flexible_rotate_deposit(30_000, 0, 25_000, False)
    >>> r.milestone_triggered_now   # 0+30k > 25k, triggers on catch-up
    True

    # Already collected — no double-charging
    >>> r = calculate_flexible_rotate_deposit(10_000, 60_000, 50_000, True)
    >>> r.milestone_triggered_now
    False
    """
    if not isinstance(deposit_amount, int) or deposit_amount <= 0:
        raise ValueError(f"deposit_amount must be a positive int. Got: {deposit_amount!r}")
    if not isinstance(assigned_value_milestone, int) or assigned_value_milestone <= 0:
        raise ValueError(f"assigned_value_milestone must be a positive int. Got: {assigned_value_milestone!r}")

    # ── Base psychological deposit fee ─────────────────────────────────────
    base: DepositFeeBreakdown = calculate_deposit_fee(deposit_amount)

    # ── Milestone detection ────────────────────────────────────────────────
    new_cumulative = current_saved_amount + deposit_amount
    should_trigger = (
        not fee_already_collected
        and new_cumulative >= assigned_value_milestone
    )

    payout_fee: int = TARGET_PAYOUT_FEE if should_trigger else 0
    final_charge: int = base.charge_amount + payout_fee

    return FlexibleRotateDepositResult(
        deposit_amount=deposit_amount,
        base_charge_amount=base.charge_amount,
        mtn_deposit_fee=base.mtn_fee,
        microbond_base_fee=base.platform_fee,
        hidden_payout_fee=payout_fee,
        final_charge_amount=final_charge,
        milestone_triggered_now=should_trigger,
        new_cumulative_total=new_cumulative,
        assigned_value_milestone=assigned_value_milestone,
    )


def get_milestone_label(pct: float) -> str:
    """Human-readable audit label for a milestone percentage."""
    return MILESTONE_LABEL.get(pct, "UNKNOWN")
