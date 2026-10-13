"""
target_goal_deposit_fee_engine.py
─────────────────────────────────────────────────────────────────────────────
Target / Goal-Based Savings Group — Deposit Fee Engine

CONTEXT:
  In a Target Group, all members pool money toward a shared milestone
  (e.g., Christmas bonuses, land down-payment, event budget). The payout
  fires either when the group reaches its monetary goal OR when the target
  date arrives — NOT on a fixed round schedule like a Rotate group.

  Because there are no numbered "rounds", we cannot pin the hidden fee to
  a round index. Instead we anchor to PERCENTAGE MILESTONES of each member's
  individual target commitment.

STRATEGY: Dynamic Percentage Milestone Recovery
  When a member joins and commits to saving a target amount (e.g. 200,000 UGX),
  the system rolls one of three milestone thresholds using numpy.random:

    • EARLY   — Fee charged when the member crosses  20% of their goal
    • MID     — Fee charged when the member crosses  50% of their goal
    • CLOSING — Fee charged on the deposit that reaches 100% of their goal

  On the deposit that pushes the member's cumulative saved amount past their
  assigned threshold, the 979 UGX payout fee is silently embedded in the
  charge. The `payout_fee_collected` flag in the DB is then flipped to True,
  ensuring the fee is never double-charged.

  Result:
    • The group reaches its exact target with zero shortfall.
    • Members collect the full, clean goal amount with no exit deduction.
    • Microbond collects exactly 979 UGX per payout-eligible member, guaranteed.

USAGE:
  # Step 1: On member join — assign their milestone (store in DB)
  from app.api.routes.group.target_savings.target_goal_deposit_fee_engine import (
      assign_member_target_milestone,
  )
  milestone = assign_member_target_milestone()
  # e.g. 0.50 → store as member.fee_milestone_threshold = 0.50

  # Step 2: On every deposit — calculate exact charge
  from app.api.routes.group.target_savings.target_goal_deposit_fee_engine import (
      calculate_target_group_deposit,
  )
  result = calculate_target_group_deposit(
      deposit_amount=30_000,
      current_saved_amount=80_000,
      target_goal_amount=200_000,
      assigned_milestone_threshold=member.fee_milestone_threshold,
      fee_already_collected=member.payout_fee_collected,
  )
  # Pass result.final_charge_amount to MTN RequestToPay
  # If result.milestone_triggered_now: flip member.payout_fee_collected = True in DB
─────────────────────────────────────────────────────────────────────────────
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np

from app.core.fee_engine import calculate_deposit_fee, DepositFeeBreakdown


# ── Constants ──────────────────────────────────────────────────────────────

# MTN MoMo flat fee charged per disbursement
MTN_FLAT_PAYOUT_FEE: int = 300  # UGX

# Microbond platform profit retained per payout
MICROBOND_PAYOUT_PROFIT: int = 679  # UGX

# Total payout cost recovered per member per payout cycle
TARGET_PAYOUT_FEE: int = MTN_FLAT_PAYOUT_FEE + MICROBOND_PAYOUT_PROFIT  # 979 UGX

# The three percentage thresholds at which the hidden fee can be triggered:
#   0.20 = EARLY   (when member crosses 20% of their savings goal)
#   0.50 = MID     (when member crosses 50% of their savings goal)
#   1.00 = CLOSING (when member crosses 100% i.e. goal completion deposit)
MILESTONE_THRESHOLDS: list[float] = [0.20, 0.50, 1.00]

# Human-readable labels for logging / audit
MILESTONE_LABEL: dict[float, str] = {
    0.20: "EARLY_20",
    0.50: "MID_50",
    1.00: "CLOSING_100",
}


# ── Data Model ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TargetDepositCalculation:
    """
    Immutable result of a single deposit calculation in a Target Savings Group.

    Attributes
    ----------
    deposit_amount : int
        The raw UGX amount the member intends to add this deposit.
    base_charge_amount : int
        Standard charge (deposit + MTN 1.5% + Microbond psychological fee),
        before any payout amortization.
    mtn_deposit_fee : int
        MTN's 1.5% collection fee component.
    microbond_deposit_fee : int
        Microbond's psychological base platform fee.
    hidden_payout_fee : int
        979 UGX if this is the milestone deposit, 0 otherwise.
    final_charge_amount : int
        Exact figure sent to MTN RequestToPay. This is what appears on
        the member's MoMo PIN prompt.
    is_fee_milestone : bool
        True if this deposit triggers the one-time hidden payout fee.
        Use this flag to flip `payout_fee_collected = True` in the DB.
    milestone_triggered_now : bool
        Alias of is_fee_milestone — for semantic clarity in the deposit pipeline.
    """
    deposit_amount: int
    base_charge_amount: int
    mtn_deposit_fee: int
    microbond_deposit_fee: int
    hidden_payout_fee: int
    final_charge_amount: int
    is_fee_milestone: bool
    milestone_triggered_now: bool

    def to_dict(self) -> dict:
        """JSON-serializable representation for API response / audit logging."""
        return {
            "deposit_amount": self.deposit_amount,
            "base_charge_amount": self.base_charge_amount,
            "mtn_deposit_fee": self.mtn_deposit_fee,
            "microbond_deposit_fee": self.microbond_deposit_fee,
            "hidden_payout_fee": self.hidden_payout_fee,
            "final_charge_amount": self.final_charge_amount,
            "is_fee_milestone": self.is_fee_milestone,
        }


# ── Public API ─────────────────────────────────────────────────────────────

def assign_member_target_milestone(random_seed: Optional[int] = None) -> float:
    """
    Randomly assign a percentage milestone threshold to a member at join time.
    The result must be stored in the database immediately (e.g. as
    `GroupMembership.fee_milestone_threshold`).

    Called ONCE per member when they commit to a target savings goal.
    Never called again for the same goal — the result is immutable.

    Parameters
    ----------
    random_seed : int, optional
        Fix numpy seed for reproducible assignment (use in tests only).

    Returns
    -------
    float
        One of: 0.20 (EARLY), 0.50 (MID), 1.00 (CLOSING).

    Example
    -------
    >>> assign_member_target_milestone()
    0.5   # Member will pay the fee when they cross 50% of their goal
    """
    rng = np.random.default_rng(random_seed)
    return float(rng.choice(MILESTONE_THRESHOLDS))


def calculate_target_group_deposit(
    deposit_amount: int,
    current_saved_amount: int,
    target_goal_amount: int,
    assigned_milestone_threshold: float,
    fee_already_collected: bool,
) -> TargetDepositCalculation:
    """
    Calculate the exact MTN RequestToPay charge for a deposit in a
    Target / Goal-Based Savings Group.

    Injects the 979 UGX payout fee on the first deposit where the member's
    cumulative savings crosses their assigned milestone threshold. All other
    deposits carry only the standard psychological pricing fees.

    Parameters
    ----------
    deposit_amount : int
        The UGX amount the member is depositing right now.
    current_saved_amount : int
        The member's cumulative savings BEFORE this deposit (from DB).
    target_goal_amount : int
        The member's total savings commitment for this group goal.
    assigned_milestone_threshold : float
        The pre-stored milestone (0.20, 0.50, or 1.00) assigned at join time.
    fee_already_collected : bool
        True if the 979 UGX payout fee has already been collected from
        this member in a previous deposit. If True, no fee is added.

    Returns
    -------
    TargetDepositCalculation
        Contains the final_charge_amount to pass to MTN RequestToPay, plus
        is_fee_milestone=True if the DB flag should now be flipped.

    Raises
    ------
    ValueError
        If deposit_amount or target_goal_amount is not a positive integer.

    Example
    -------
    >>> # Member committed 200k, saved 80k so far, milestone = 50% = 100k
    >>> r = calculate_target_group_deposit(
    ...     deposit_amount=30_000,
    ...     current_saved_amount=80_000,
    ...     target_goal_amount=200_000,
    ...     assigned_milestone_threshold=0.50,
    ...     fee_already_collected=False,
    ... )
    >>> r.is_fee_milestone   # 80k+30k=110k > 100k (50%) → milestone crossed
    True
    >>> r.hidden_payout_fee
    979
    """
    if not isinstance(deposit_amount, int) or deposit_amount <= 0:
        raise ValueError(f"deposit_amount must be a positive int. Got: {deposit_amount!r}")
    if not isinstance(target_goal_amount, int) or target_goal_amount <= 0:
        raise ValueError(f"target_goal_amount must be a positive int. Got: {target_goal_amount!r}")
    if assigned_milestone_threshold not in MILESTONE_THRESHOLDS:
        raise ValueError(
            f"assigned_milestone_threshold must be one of {MILESTONE_THRESHOLDS}. "
            f"Got: {assigned_milestone_threshold!r}"
        )

    # ── Base psychological deposit fees (same as all other group types) ──
    base: DepositFeeBreakdown = calculate_deposit_fee(deposit_amount)

    # ── Milestone detection ────────────────────────────────────────────────
    should_charge_milestone = False

    if not fee_already_collected:
        new_cumulative = current_saved_amount + deposit_amount
        threshold_amount = target_goal_amount * assigned_milestone_threshold

        # Trigger if this deposit pushes the member past their assigned percentage,
        # or if it completes/exceeds the full goal (catches corner cases).
        if new_cumulative >= threshold_amount or new_cumulative >= target_goal_amount:
            should_charge_milestone = True

    payout_fee: int = TARGET_PAYOUT_FEE if should_charge_milestone else 0
    final_charge: int = base.charge_amount + payout_fee

    return TargetDepositCalculation(
        deposit_amount=deposit_amount,
        base_charge_amount=base.charge_amount,
        mtn_deposit_fee=base.mtn_fee,
        microbond_deposit_fee=base.platform_fee,
        hidden_payout_fee=payout_fee,
        final_charge_amount=final_charge,
        is_fee_milestone=should_charge_milestone,
        milestone_triggered_now=should_charge_milestone,
    )


def get_milestone_label(threshold: float) -> str:
    """
    Return the human-readable audit label for a milestone threshold.
    Safe to call with any stored DB value — returns 'UNKNOWN' if unrecognized.
    """
    return MILESTONE_LABEL.get(threshold, "UNKNOWN")
