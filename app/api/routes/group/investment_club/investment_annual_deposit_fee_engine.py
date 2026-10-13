"""
investment_annual_deposit_fee_engine.py
─────────────────────────────────────────────────────────────────────────────
Investment Club (Open-Ended Chama) — Deposit Fee Engine

CONTEXT:
  Investment Clubs operate on an open-ended, share-based model. Members
  continuously buy shares (e.g. 1 share = 10,000 UGX) weekly or monthly,
  and dividends are distributed annually during a "Share Out" event.

  Because there is no fixed end date and no fixed savings goal, we cannot
  anchor the hidden fee to round indexes (Rotate strategy) or to percentage
  milestones (Target strategy).

  Instead, we anchor to the ACCOUNTING YEAR CYCLE — the natural annual
  rhythm every Investment Club already follows.

STRATEGY: Annual Streak Deposit Count Milestone
  At the start of every accounting year, each member is randomly assigned
  one of three deposit-count milestones using numpy.random:

    • EARLY  — hidden fee applied on their  1st deposit of the year
    • MID    — hidden fee applied on their  4th deposit of the year
    • LATE   — hidden fee applied on their  8th deposit of the year

  On the deposit that reaches or EXCEEDS their assigned count (to handle
  members who missed weeks and are catching up), the 979 UGX payout fee
  is silently embedded in the MoMo PIN prompt. The `fee_collected_this_year`
  DB flag is then flipped to True for the remainder of the accounting year.

  At year-end, a cron job resets ALL members:
    • current_annual_deposit_count = 0
    • fee_collected_this_year = False
    • Assigns a fresh random milestone for the new year

  Result:
    • Annual Share Out distributes exactly the committed dividend amount.
    • Members receive mathematically perfect dividends with zero deductions.
    • Microbond collects exactly 979 UGX per member per year.

USAGE:
  # Step 1: New year reset — assign each member's milestone for the year (store in DB)
  from app.api.routes.group.investment_club.investment_annual_deposit_fee_engine import (
      assign_member_annual_milestone,
  )
  milestone = assign_member_annual_milestone()
  # e.g. 4 → store as member.annual_fee_milestone_count = 4

  # Step 2: On every deposit — calculate exact charge
  from app.api.routes.group.investment_club.investment_annual_deposit_fee_engine import (
      calculate_investment_group_deposit,
  )
  result = calculate_investment_group_deposit(
      deposit_amount=10_000,
      current_annual_deposit_count=member.current_annual_deposit_count,
      assigned_milestone_count=member.annual_fee_milestone_count,
      fee_collected_this_year=member.fee_collected_this_year,
  )
  # Pass result.final_charge_amount to MTN RequestToPay.
  # If result.is_fee_milestone:
  #   member.fee_collected_this_year = True (commit to DB)
  # Always increment: member.current_annual_deposit_count += 1
─────────────────────────────────────────────────────────────────────────────
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np

from app.core.fee_engine import calculate_deposit_fee, DepositFeeBreakdown


# ── Constants ──────────────────────────────────────────────────────────────

# MTN MoMo flat fee charged per disbursement (bulk Share Out payout)
MTN_FLAT_PAYOUT_FEE: int = 300  # UGX

# Microbond platform profit per member per annual payout
MICROBOND_PAYOUT_PROFIT: int = 679  # UGX

# Total cost recovered per member per accounting year
TARGET_PAYOUT_FEE: int = MTN_FLAT_PAYOUT_FEE + MICROBOND_PAYOUT_PROFIT  # 979 UGX

# The three deposit-count milestones within an accounting year at which
# the hidden fee can be triggered:
#   1 = EARLY  (first deposit of the year)
#   4 = MID    (fourth deposit of the year)
#   8 = LATE   (eighth deposit of the year)
DEPOSIT_COUNT_MILESTONES: list[int] = [1, 4, 8]

# Human-readable labels for logging / audit
MILESTONE_LABEL: dict[int, str] = {
    1: "EARLY_1ST",
    4: "MID_4TH",
    8: "LATE_8TH",
}


# ── Data Model ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class InvestmentDepositCalculation:
    """
    Immutable result of a single deposit calculation in an Investment Club.

    Attributes
    ----------
    deposit_amount : int
        The raw UGX amount the member is adding this deposit (share purchase).
    base_charge_amount : int
        Standard charge (deposit + MTN 1.5% + Microbond psychological fee),
        before any annual payout amortization.
    mtn_deposit_fee : int
        MTN's 1.5% collection fee component.
    microbond_deposit_fee : int
        Microbond's psychological base platform fee.
    hidden_payout_fee : int
        979 UGX if this is the annual milestone deposit, 0 otherwise.
    final_charge_amount : int
        Exact figure sent to MTN RequestToPay — shown on member's MoMo prompt.
    is_fee_milestone : bool
        True if this deposit triggers the one-time annual payout fee.
        Use this flag to:
          1. Flip `fee_collected_this_year = True` in the DB.
          2. Increment `current_annual_deposit_count` by 1 in the DB.
    this_deposit_number : int
        The sequential deposit number this transaction represents
        within the current accounting year (current_count + 1).
    """
    deposit_amount: int
    base_charge_amount: int
    mtn_deposit_fee: int
    microbond_deposit_fee: int
    hidden_payout_fee: int
    final_charge_amount: int
    is_fee_milestone: bool
    this_deposit_number: int

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
            "this_deposit_number": self.this_deposit_number,
        }


# ── Public API ─────────────────────────────────────────────────────────────

def assign_member_annual_milestone(random_seed: Optional[int] = None) -> int:
    """
    Randomly assign a deposit-count milestone to a member for the upcoming
    accounting year. The result must be stored in the database immediately.

    Called ONCE per member per accounting year — either when they join the
    club, or by the New Year cron job that resets all member counters.

    Parameters
    ----------
    random_seed : int, optional
        Fix numpy seed for reproducible assignment (use in tests only).

    Returns
    -------
    int
        One of: 1 (EARLY), 4 (MID), 8 (LATE).

    Example
    -------
    >>> assign_member_annual_milestone()
    4   # Member will pay the fee on their 4th deposit of the year
    """
    rng = np.random.default_rng(random_seed)
    return int(rng.choice(DEPOSIT_COUNT_MILESTONES))


def calculate_investment_group_deposit(
    deposit_amount: int,
    current_annual_deposit_count: int,
    assigned_milestone_count: int,
    fee_collected_this_year: bool,
) -> InvestmentDepositCalculation:
    """
    Calculate the exact MTN RequestToPay charge for a share purchase deposit
    in an Investment Club / Open-Ended Chama.

    Injects the 979 UGX annual payout fee on the first deposit where the
    member's annual deposit counter reaches or exceeds their assigned
    milestone count. All prior deposits are standard. Once triggered, all
    remaining deposits that year are also standard.

    The >= comparison (not ==) is intentional: it handles catch-up deposits
    where a member missed weeks and their count jumps past the milestone in
    a single transaction without having triggered it on the exact target deposit.

    Parameters
    ----------
    deposit_amount : int
        The UGX amount being deposited right now (1+ full shares).
    current_annual_deposit_count : int
        The member's deposit count for the current accounting year BEFORE
        this deposit (read from DB before processing).
    assigned_milestone_count : int
        The pre-stored milestone (1, 4, or 8) assigned at the start of the year.
    fee_collected_this_year : bool
        True if the 979 UGX annual fee has already been collected from this
        member earlier in the current accounting year.

    Returns
    -------
    InvestmentDepositCalculation
        Contains final_charge_amount for MTN RequestToPay and is_fee_milestone
        to drive the DB update.

    Raises
    ------
    ValueError
        If deposit_amount is not a positive integer, or if
        assigned_milestone_count is not one of the valid milestones.

    Example
    -------
    >>> # Member B assigned milestone=4, making their 4th deposit now
    >>> result = calculate_investment_group_deposit(
    ...     deposit_amount=10_000,
    ...     current_annual_deposit_count=3,   # 3 done already → this is 4th
    ...     assigned_milestone_count=4,
    ...     fee_collected_this_year=False,
    ... )
    >>> result.is_fee_milestone
    True
    >>> result.hidden_payout_fee
    979
    >>> result.final_charge_amount   # 10,284 (base) + 979 = 11,263
    11263
    """
    if not isinstance(deposit_amount, int) or deposit_amount <= 0:
        raise ValueError(f"deposit_amount must be a positive int. Got: {deposit_amount!r}")
    if assigned_milestone_count not in DEPOSIT_COUNT_MILESTONES:
        raise ValueError(
            f"assigned_milestone_count must be one of {DEPOSIT_COUNT_MILESTONES}. "
            f"Got: {assigned_milestone_count!r}"
        )

    # ── Base psychological deposit fees ───────────────────────────────────
    base: DepositFeeBreakdown = calculate_deposit_fee(deposit_amount)

    # ── Milestone detection ────────────────────────────────────────────────
    # This is the Nth deposit of the year (1-indexed)
    this_deposit_number: int = current_annual_deposit_count + 1

    should_charge_milestone = False
    if not fee_collected_this_year:
        # Trigger if this deposit lands ON or PAST the milestone count.
        # The >= handles catch-up: a member who was inactive for weeks might
        # jump from deposit #2 to #5 on a bulk payment — still catches the fee.
        if this_deposit_number >= assigned_milestone_count:
            should_charge_milestone = True

    payout_fee: int = TARGET_PAYOUT_FEE if should_charge_milestone else 0
    final_charge: int = base.charge_amount + payout_fee

    return InvestmentDepositCalculation(
        deposit_amount=deposit_amount,
        base_charge_amount=base.charge_amount,
        mtn_deposit_fee=base.mtn_fee,
        microbond_deposit_fee=base.platform_fee,
        hidden_payout_fee=payout_fee,
        final_charge_amount=final_charge,
        is_fee_milestone=should_charge_milestone,
        this_deposit_number=this_deposit_number,
    )


def get_milestone_label(count: int) -> str:
    """
    Return the human-readable audit label for a deposit-count milestone.
    Safe to call with any stored DB value — returns 'UNKNOWN' if unrecognized.
    """
    return MILESTONE_LABEL.get(count, "UNKNOWN")
