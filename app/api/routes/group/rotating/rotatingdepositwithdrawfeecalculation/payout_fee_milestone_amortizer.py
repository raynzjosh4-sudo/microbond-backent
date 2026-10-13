"""
payout_fee_milestone_amortizer.py
─────────────────────────────────────────────────────────────────────────────
Rotating Group (MERRY_GO_ROUND / ROSCA) — Amortized Payout Fee Engine

STRATEGY: Milestone-Based Hidden Payout Fee
  In a rotating savings group, the platform must fund two costs per payout:
    1. MTN MoMo flat disbursement fee  (MTN_FLAT_PAYOUT_FEE  = 300 UGX)
    2. Microbond platform profit        (MICROBOND_PAYOUT_PROFIT = 679 UGX)
    ──────────────────────────────────────────────────────────────────────
    Total per payout                     TARGET_PAYOUT_FEE   = 979 UGX

  Rather than deducting this from the winner's payout (which destroys trust),
  each member silently carries the fee on exactly ONE deposit during their
  cycle — randomly placed at one of three "milestone" positions:
    • Start  — their very first deposit of the cycle
    • Middle — the deposit at the halfway mark of the cycle
    • Last   — their final deposit before the cycle closes

  The milestone is chosen independently per member using numpy.random.choice,
  so no two members are guaranteed to carry the fee on the same day. This
  ensures the pattern is invisible across member comparisons and cannot be
  reverse-engineered.

  Result:
    • Every winner receives an exact, clean payout with ZERO deductions.
    • Microbond collects exactly 979 UGX per cycle per member, guaranteed.
    • The charged amounts look organic and algorithmic — not a flat tax.

HOW TO USE (called once at group creation):
  from app.api.routes.group.rotating.rotatingdepositwithdrawfeecalculation import (
      generate_milestone_deposit_schedule,
      MemberDepositSchedule,
      TARGET_PAYOUT_FEE,
  )

  schedule = generate_milestone_deposit_schedule(
      group_target_amount=100_000,
      total_members=10,
      total_rounds=10,
  )
  # schedule is a list of MemberDepositSchedule objects — one per member.
  # Persist each entry's `milestone_round_number` and `milestone_charge_amount`
  # to the database at group creation. The deposit pipeline reads these
  # values when generating each member's RequestToPay charge.
─────────────────────────────────────────────────────────────────────────────
"""

from dataclasses import dataclass
from typing import Optional

import numpy as np

from app.core.fee_engine import calculate_deposit_fee, DepositFeeBreakdown


# ── Constants ──────────────────────────────────────────────────────────────

# MTN MoMo flat fee charged per disbursement (transfer-to-mobile)
MTN_FLAT_PAYOUT_FEE: int = 300  # UGX

# Microbond profit margin retained per payout
MICROBOND_PAYOUT_PROFIT: int = 679  # UGX

# Total cost the platform must recover per payout event
TARGET_PAYOUT_FEE: int = MTN_FLAT_PAYOUT_FEE + MICROBOND_PAYOUT_PROFIT  # 979 UGX

# Milestone labels for clarity and logging
MILESTONE_START = "START"
MILESTONE_MIDDLE = "MIDDLE"
MILESTONE_LAST = "LAST"


# ── Data Models ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MemberDepositSchedule:
    """
    The complete deposit instruction set for a single group member for the
    full cycle. Generated once at group creation and stored in the database.

    Attributes
    ----------
    member_index : int
        1-based position of the member in the group (for ordering / display).
    total_rounds : int
        Total number of deposits this member will make in the cycle.
    group_target_amount : int
        The base UGX amount the member intends to save per round.
    base_charge_amount : int
        Standard charge per deposit (group_target_amount + psychological fees)
        for all non-milestone rounds.
    milestone_round_number : int
        The 1-based round index at which the hidden payout fee is applied.
    milestone_type : str
        Human-readable label: "START", "MIDDLE", or "LAST".
    milestone_charge_amount : int
        The charge for the milestone deposit = base_charge_amount + TARGET_PAYOUT_FEE.
    hidden_payout_fee : int
        Always equals TARGET_PAYOUT_FEE (979 UGX). Stored for audit purposes.
    mtn_deposit_fee : int
        MTN's 1.5% collection fee component (from the base fee engine).
    microbond_deposit_fee : int
        Microbond's psychological deposit fee (from the base fee engine).
    """
    member_index: int
    total_rounds: int
    group_target_amount: int
    base_charge_amount: int
    milestone_round_number: int
    milestone_type: str
    milestone_charge_amount: int
    hidden_payout_fee: int
    mtn_deposit_fee: int
    microbond_deposit_fee: int

    def charge_for_round(self, round_number: int) -> int:
        """
        Return the exact charge amount for a given 1-based round number.
        The deposit pipeline calls this when building the MTN RequestToPay.

        Parameters
        ----------
        round_number : int
            The 1-based round index (1 = first deposit, total_rounds = last).

        Returns
        -------
        int
            The exact UGX figure to send to MTN RequestToPay for this deposit.
        """
        if round_number == self.milestone_round_number:
            return self.milestone_charge_amount
        return self.base_charge_amount

    def to_dict(self) -> dict:
        """JSON-serializable representation for database storage."""
        return {
            "member_index": self.member_index,
            "total_rounds": self.total_rounds,
            "group_target_amount": self.group_target_amount,
            "base_charge_amount": self.base_charge_amount,
            "milestone_round_number": self.milestone_round_number,
            "milestone_type": self.milestone_type,
            "milestone_charge_amount": self.milestone_charge_amount,
            "hidden_payout_fee": self.hidden_payout_fee,
            "mtn_deposit_fee": self.mtn_deposit_fee,
            "microbond_deposit_fee": self.microbond_deposit_fee,
        }


# ── Internal Helpers ───────────────────────────────────────────────────────

def _resolve_milestone_round(total_rounds: int, milestone_type: str) -> int:
    """
    Convert a milestone label to its actual 1-based round number.

    Parameters
    ----------
    total_rounds : int
        The total number of deposit rounds in the cycle.
    milestone_type : str
        One of: MILESTONE_START, MILESTONE_MIDDLE, MILESTONE_LAST.

    Returns
    -------
    int
        The 1-based round index at which the fee will be applied.
    """
    if milestone_type == MILESTONE_START:
        return 1
    elif milestone_type == MILESTONE_MIDDLE:
        # Integer floor division — for 10 rounds this gives round 5
        return max(1, total_rounds // 2)
    else:  # MILESTONE_LAST
        return total_rounds


def _pick_milestone_for_member(rng: np.random.Generator) -> str:
    """
    Randomly select one of the three milestone positions for a single member
    using the provided numpy random Generator (reproducible if seeded).

    Parameters
    ----------
    rng : numpy.random.Generator
        A numpy random generator instance (use numpy.random.default_rng).

    Returns
    -------
    str
        One of: MILESTONE_START, MILESTONE_MIDDLE, MILESTONE_LAST.
    """
    options = [MILESTONE_START, MILESTONE_MIDDLE, MILESTONE_LAST]
    return rng.choice(options)


# ── Public API ─────────────────────────────────────────────────────────────

def generate_milestone_deposit_schedule(
    group_target_amount: int,
    total_members: int,
    total_rounds: int,
    random_seed: Optional[int] = None,
) -> list[MemberDepositSchedule]:
    """
    Generate the complete deposit schedule for all members of a rotating
    savings group. Must be called ONCE at group creation and persisted.

    For each member, the hidden payout fee (979 UGX) is placed on exactly
    ONE randomly chosen deposit — either the START, MIDDLE, or LAST round
    of that member's cycle. All other deposits use the standard base amount.

    Parameters
    ----------
    group_target_amount : int
        The per-round savings target each member is committing to (e.g. 100,000).
    total_members : int
        Number of members in the rotating group.
    total_rounds : int
        Number of deposit rounds per cycle (typically equals total_members in
        a standard ROSCA, but can differ for multi-payout configurations).
    random_seed : int, optional
        Fix the numpy random seed for fully reproducible schedules (useful in
        testing and idempotent re-generation). Leave None for production use.

    Returns
    -------
    list[MemberDepositSchedule]
        One MemberDepositSchedule per member, in member_index order (1-based).
        Persist these objects to the database immediately after group creation.

    Raises
    ------
    ValueError
        If any input argument is invalid (non-positive integers, etc.).

    Example
    -------
    >>> schedule = generate_milestone_deposit_schedule(
    ...     group_target_amount=100_000,
    ...     total_members=10,
    ...     total_rounds=10,
    ... )
    >>> for s in schedule[:3]:
    ...     print(f"Member {s.member_index}: milestone={s.milestone_type} "
    ...           f"round={s.milestone_round_number}, "
    ...           f"charge={s.milestone_charge_amount:,} UGX")
    Member 1: milestone=LAST   round=10, charge=103,960 UGX
    Member 2: milestone=START  round=1,  charge=103,960 UGX
    Member 3: milestone=MIDDLE round=5,  charge=103,960 UGX
    """
    # ── Validation ────────────────────────────────────────────────────────
    if not isinstance(group_target_amount, int) or group_target_amount <= 0:
        raise ValueError(f"group_target_amount must be a positive int. Got: {group_target_amount!r}")
    if not isinstance(total_members, int) or total_members < 2:
        raise ValueError(f"total_members must be >= 2. Got: {total_members!r}")
    if not isinstance(total_rounds, int) or total_rounds < 1:
        raise ValueError(f"total_rounds must be >= 1. Got: {total_rounds!r}")

    # ── Base fee breakdown (same for all members, all non-milestone rounds) ─
    base: DepositFeeBreakdown = calculate_deposit_fee(group_target_amount)

    # ── Reproducible numpy random generator ──────────────────────────────
    rng = np.random.default_rng(random_seed)

    schedules: list[MemberDepositSchedule] = []

    for member_index in range(1, total_members + 1):
        # Pick this member's secret milestone independently
        milestone_type: str = _pick_milestone_for_member(rng)
        milestone_round: int = _resolve_milestone_round(total_rounds, milestone_type)
        milestone_charge: int = base.charge_amount + TARGET_PAYOUT_FEE

        schedules.append(
            MemberDepositSchedule(
                member_index=member_index,
                total_rounds=total_rounds,
                group_target_amount=group_target_amount,
                base_charge_amount=base.charge_amount,
                milestone_round_number=milestone_round,
                milestone_type=milestone_type,
                milestone_charge_amount=milestone_charge,
                hidden_payout_fee=TARGET_PAYOUT_FEE,
                mtn_deposit_fee=base.mtn_fee,
                microbond_deposit_fee=base.platform_fee,
            )
        )

    return schedules


def get_charge_for_deposit(
    group_target_amount: int,
    member_milestone_round: int,
    current_round_number: int,
) -> int:
    """
    Lightweight helper for the deposit pipeline: given a member's pre-stored
    milestone round and the current round, return the exact charge amount to
    send to MTN RequestToPay.

    This avoids re-loading the full schedule from the database; instead the
    pipeline only needs to persist `milestone_round_number` per member.

    Parameters
    ----------
    group_target_amount : int
        The member's per-round savings target.
    member_milestone_round : int
        The 1-based round number at which this member carries the payout fee.
        Retrieved from the database at deposit time.
    current_round_number : int
        The 1-based round number being processed right now.

    Returns
    -------
    int
        Exact UGX amount to pass to MTN RequestToPay.
    """
    base: DepositFeeBreakdown = calculate_deposit_fee(group_target_amount)
    if current_round_number == member_milestone_round:
        return base.charge_amount + TARGET_PAYOUT_FEE
    return base.charge_amount
