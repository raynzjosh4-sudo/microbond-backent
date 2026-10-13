"""
rotating_ledger_evaluator.py
─────────────────────────────────────────────────────────────────────────────
Rotating Group — Ledger-Based Balance Evaluator

THE CORE PHILOSOPHY: "What do you owe today?" not "Did you pay Day 3?"
  A rigid daily calendar breaks the moment a user pays in advance or misses
  a day. A ledger system ONLY asks one question per evaluation:

    expected_balance_today  vs  actual_paid_balance

  The expected balance is calculated from the group schedule:
    expected = contribution_amount × (days_elapsed / collection_frequency_days)

  If actual >= expected  → Member is AHEAD. Silence all reminders.
  If actual == expected  → Member is ON_TRACK. No action needed.
  If actual <  expected  → Member is BEHIND. Show arrears dashboard.
                           Calculate catch-up amount.

  This single comparison drives:
    1. The deposit dashboard (green / amber / red card)
    2. The cron job's reminder engine (send SMS or stay silent)
    3. The deposit screen (pre-fills the catch-up amount)
    4. The MemberObligation update logic (mark PAID vs LATE)

EXAMPLE SCENARIOS:
  ┌──────────────────────────────────────────────────────────────────┐
  │ Group: 10,000 UGX daily, member paid 100,000 on Day 1           │
  │                                                                  │
  │ Day 5 evaluation:                                                │
  │   expected = 10,000 × 5 = 50,000 UGX                           │
  │   actual   = 100,000 UGX                                        │
  │   status   = AHEAD by 50,000 UGX (5 days ahead)                │
  │   reminders: SILENCED                                           │
  │   days_until_next_reminder: 5                                   │
  │                                                                  │
  │ Day 12 evaluation (advance ran out):                            │
  │   expected = 10,000 × 12 = 120,000 UGX                         │
  │   actual   = 100,000 UGX                                        │
  │   status   = BEHIND by 20,000 UGX (2 days in arrears)          │
  │   reminders: ACTIVE                                             │
  │   catch_up_amount: 20,000 UGX                                   │
  └──────────────────────────────────────────────────────────────────┘

USAGE:
  from app.api.routes.group.rotating.rotatingdepositwithdrawfeecalculation.rotating_ledger_evaluator import (
      evaluate_member_ledger,
      LedgerStatus,
      LedgerEvaluation,
  )

  eval_result = evaluate_member_ledger(
      contribution_amount        = int(rot.contribution_amount),
      collection_frequency_days  = rot.collection_frequency_days,
      group_start_time_ms        = rot.group_start_time,
      actual_paid_balance        = membership.total_contributed,
      current_time_ms            = None,   # None = use current UTC time
      unpaid_penalties_ugx       = penalties_sum,
  )

  # Drive the dashboard card color:
  if eval_result.status == LedgerStatus.BEHIND:
      show_red_arrears_card(catch_up=eval_result.catch_up_amount)
  elif eval_result.status == LedgerStatus.AHEAD:
      show_green_card(days_ahead=eval_result.days_ahead)

  # Drive the cron reminder:
  if eval_result.should_send_reminder:
      send_sms_reminder(...)
─────────────────────────────────────────────────────────────────────────────
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# ── Enums ──────────────────────────────────────────────────────────────────

class LedgerStatus(str, Enum):
    """
    The member's payment standing relative to the group schedule today.
    """
    AHEAD     = "AHEAD"      # Paid more than expected — reminders silenced
    ON_TRACK  = "ON_TRACK"   # Exactly on schedule — no action needed
    BEHIND    = "BEHIND"     # Owes arrears — show red card + reminder


# ── Data Model ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class LedgerEvaluation:
    """
    The complete ledger snapshot for a single member at the moment of evaluation.

    Attributes
    ----------
    status : LedgerStatus
        AHEAD, ON_TRACK, or BEHIND.
    expected_balance_today : int
        Total UGX the member SHOULD have contributed based on the schedule
        and days elapsed since the group started.
    actual_paid_balance : int
        Total UGX the member HAS contributed (from total_contributed in DB).
    net_balance : int
        actual_paid_balance - expected_balance_today.
        Positive = ahead, 0 = on track, negative = in arrears.
    catch_up_amount : int
        The exact UGX the member needs to deposit RIGHT NOW to come back
        to on-track status. 0 if status is AHEAD or ON_TRACK.
        Includes unpaid penalties.
    days_ahead : int
        How many full collection periods ahead the member's payment covers.
        0 if status is BEHIND or ON_TRACK.
    days_in_arrears : int
        How many full collection periods the member has missed.
        0 if status is AHEAD or ON_TRACK.
    should_send_reminder : bool
        True if the cron job should dispatch an SMS/Push reminder.
        False if the member is AHEAD or ON_TRACK (silence reminders).
    unpaid_penalties_ugx : int
        Total uncleared late fee penalties (echoed for completeness).
    days_elapsed : int
        Calendar days since the group started (for debugging/audit).
    periods_elapsed : float
        Decimal number of full collection periods elapsed (e.g. 2.5 periods).
    expected_periods_paid : int
        Floor of periods_elapsed — the whole number of periods the member
        should have fully paid by now.
    """
    status: LedgerStatus
    expected_balance_today: int
    actual_paid_balance: int
    net_balance: int
    catch_up_amount: int
    days_ahead: int
    days_in_arrears: int
    should_send_reminder: bool
    unpaid_penalties_ugx: int
    days_elapsed: int
    periods_elapsed: float
    expected_periods_paid: int

    def to_dict(self) -> dict:
        """JSON-serializable for deposit-info API response and cron logs."""
        return {
            "status": self.status.value,
            "expected_balance_today": self.expected_balance_today,
            "actual_paid_balance": self.actual_paid_balance,
            "net_balance": self.net_balance,
            "catch_up_amount": self.catch_up_amount,
            "days_ahead": self.days_ahead,
            "days_in_arrears": self.days_in_arrears,
            "should_send_reminder": self.should_send_reminder,
            "unpaid_penalties_ugx": self.unpaid_penalties_ugx,
            "days_elapsed": self.days_elapsed,
            "periods_elapsed": round(self.periods_elapsed, 2),
            "expected_periods_paid": self.expected_periods_paid,
        }

    @property
    def dashboard_color(self) -> str:
        """Flutter dashboard card color token driven by ledger status."""
        return {
            LedgerStatus.AHEAD:    "GREEN",
            LedgerStatus.ON_TRACK: "BLUE",
            LedgerStatus.BEHIND:   "RED",
        }[self.status]

    @property
    def dashboard_label(self) -> str:
        """Short label for the mobile dashboard card."""
        if self.status == LedgerStatus.AHEAD:
            return f"Paid ahead — {self.days_ahead} day(s) covered"
        if self.status == LedgerStatus.ON_TRACK:
            return "On track"
        return f"Arrears: {self.catch_up_amount:,} UGX"


# ── Public API ─────────────────────────────────────────────────────────────

def evaluate_member_ledger(
    contribution_amount: int,
    collection_frequency_days: int,
    group_start_time_ms: int,
    actual_paid_balance: int,
    unpaid_penalties_ugx: int = 0,
    current_time_ms: Optional[int] = None,
    effective_start_time_ms: Optional[int] = None,
) -> LedgerEvaluation:
    """
    Evaluate a member's payment standing in a Rotating Group using the
    ledger model: expected balance vs actual paid balance.

    Called by:
      - The deposit-info endpoint (to populate the dashboard + pre-fill catch-up)
      - The cron job reminder engine (to decide whether to send SMS/Push)
      - Post-deposit obligation update logic (to determine new status)

    Parameters
    ----------
    contribution_amount : int
        The per-period contribution target (e.g. 10,000 UGX per week).
        From RotatingGroupDetails.contribution_amount.
    collection_frequency_days : int
        How many calendar days between required contributions (e.g. 7 for weekly,
        1 for daily, 30 for monthly).
        From RotatingGroupDetails.collection_frequency_days.
    group_start_time_ms : int
        Unix epoch milliseconds when the group's first collection period began.
        From RotatingGroupDetails.group_start_time.
    actual_paid_balance : int
        The member's running cumulative total contributions (UGX).
        From GroupMembership.total_contributed.
    unpaid_penalties_ugx : int, optional
        Sum of all uncleared GroupPenalty rows for this member. Included in
        catch_up_amount so the deposit screen shows the complete amount owed.
        Defaults to 0.
    effective_start_time_ms : int, optional
        The timestamp from which this member's obligation clock starts.
        ┌─────────────────────────────────────────────────────────────┐
        │ FOUNDING MEMBER  → pass group_start_time_ms (same as group) │
        │ MID-CYCLE JOINER → pass membership.joined_at               │
        │                    (their personal obligation clock start)   │
        └─────────────────────────────────────────────────────────────┘
        If None, falls back to group_start_time_ms (safe default).
        This prevents new joiners from seeing false arrears for cycles
        that happened before they even downloaded the app.
    current_time_ms : int, optional
        Override the current time (Unix epoch ms). Defaults to UTC now.
        Use for testing or backdated evaluations.

    Returns
    -------
    LedgerEvaluation
        Complete ledger snapshot. Use .status, .catch_up_amount,
        .should_send_reminder, and .dashboard_label to drive the UI + cron.

    Raises
    ------
    ValueError
        If contribution_amount or collection_frequency_days is not positive.

    Examples
    --------
    >>> import time
    >>> start = int(time.time() * 1000) - (5 * 86_400_000)  # 5 days ago
    >>> # Daily group, member paid 100,000 (10 days advance) on Day 1
    >>> e = evaluate_member_ledger(10_000, 1, start, 100_000)
    >>> e.status
    <LedgerStatus.AHEAD: 'AHEAD'>
    >>> e.days_ahead
    95   # 100,000 / 10,000 = 10 days paid - 5 elapsed = 5 days ahead
    >>> e.should_send_reminder
    False
    """
    if not isinstance(contribution_amount, int) or contribution_amount <= 0:
        raise ValueError(f"contribution_amount must be a positive int. Got: {contribution_amount!r}")
    if not isinstance(collection_frequency_days, int) or collection_frequency_days <= 0:
        raise ValueError(f"collection_frequency_days must be a positive int. Got: {collection_frequency_days!r}")

    # ── Elapsed time calculation ───────────────────────────────────────────
    now_ms = current_time_ms if current_time_ms is not None else int(
        datetime.now(timezone.utc).timestamp() * 1000
    )
    # KEY: Use the member's personal obligation clock start.
    # For founding members this equals group_start_time_ms.
    # For mid-cycle joiners this equals their joined_at timestamp.
    # This prevents showing false arrears for pre-join cycles.
    obligation_start_ms = effective_start_time_ms if effective_start_time_ms is not None else group_start_time_ms
    # Clamp to 0: if group hasn't started yet, no obligation exists
    elapsed_ms = max(0, now_ms - obligation_start_ms)
    days_elapsed = elapsed_ms // 86_400_000  # ms → full calendar days

    # How many full collection periods have elapsed?
    periods_elapsed = days_elapsed / collection_frequency_days
    expected_periods = int(periods_elapsed)  # floor: whole periods due

    # ── Expected vs actual ────────────────────────────────────────────────
    expected_balance = expected_periods * contribution_amount
    net_balance = actual_paid_balance - expected_balance

    # ── Classify standing ─────────────────────────────────────────────────
    if net_balance > 0:
        # Member is ahead — how many full future periods does the surplus cover?
        days_ahead = int(net_balance // contribution_amount) * collection_frequency_days
        days_in_arrears = 0
        catch_up_amount = 0
        status = LedgerStatus.AHEAD
        should_remind = False

    elif net_balance == 0:
        days_ahead = 0
        days_in_arrears = 0
        catch_up_amount = unpaid_penalties_ugx  # only penalties if any
        status = LedgerStatus.ON_TRACK
        should_remind = False  # exactly on schedule — no nudge needed

    else:
        # Member is behind — calculate the catch-up amount
        arrears_ugx = abs(net_balance)
        days_in_arrears = int(arrears_ugx // contribution_amount) * collection_frequency_days
        days_ahead = 0
        # Catch-up = arrears + any unpaid late fee penalties
        catch_up_amount = arrears_ugx + unpaid_penalties_ugx
        status = LedgerStatus.BEHIND
        should_remind = True

    return LedgerEvaluation(
        status=status,
        expected_balance_today=expected_balance,
        actual_paid_balance=actual_paid_balance,
        net_balance=net_balance,
        catch_up_amount=catch_up_amount,
        days_ahead=days_ahead,
        days_in_arrears=days_in_arrears,
        should_send_reminder=should_remind,
        unpaid_penalties_ugx=unpaid_penalties_ugx,
        days_elapsed=int(days_elapsed),
        periods_elapsed=periods_elapsed,
        expected_periods_paid=expected_periods,
    )


# ── Mid-Cycle Join Policy Helpers ──────────────────────────────────────────

class MidCycleJoinPolicy(str, Enum):
    """
    Configures how a new member joining an already-active Rotating Group
    is treated with respect to their financial obligation.

    Store as a field on RotatingGroupDetails (e.g. mid_cycle_join_policy).
    """
    FRESH_START = "FRESH_START"
    # Member owes NOTHING for cycles before they joined.
    # Ledger clock starts at their joined_at timestamp.
    # They are added to the END of the payout queue.
    # Best for: open-enrollment groups, replacing a dropped member.

    BUY_IN_REQUIRED = "BUY_IN_REQUIRED"
    # Member pays a lump-sum equal to:
    #   contribution_amount x full_cycles_completed_before_joining
    # This keeps the pool balanced so existing members are not
    # disadvantaged by a newcomer receiving a payout without
    # having contributed equally from the start.
    # Best for: strict closed groups adding a late replacement.


def calculate_buy_in_amount(
    contribution_amount: int,
    collection_frequency_days: int,
    group_start_time_ms: int,
    member_joined_at_ms: int,
    current_time_ms: Optional[int] = None,
) -> dict:
    """
    Calculate the lump-sum buy-in a new mid-cycle joiner must pay when
    the group policy is BUY_IN_REQUIRED.

    This ensures the pool is never short-changed: the buy-in covers exactly
    the contribution the member "missed" for each completed cycle that
    finished before their join date.

    Parameters
    ----------
    contribution_amount : int
        Per-cycle contribution target (e.g. 10,000 UGX per week).
    collection_frequency_days : int
        Days between contributions (1=daily, 7=weekly, 30=monthly).
    group_start_time_ms : int
        Unix epoch ms when the group started its first collection period.
    member_joined_at_ms : int
        Unix epoch ms when the member's join was approved (membership.joined_at).
    current_time_ms : int, optional
        Override current time (ms). Defaults to UTC now. Use for testing.

    Returns
    -------
    dict with keys:
      buy_in_amount_ugx  — exact UGX lump-sum the member must pay
      cycles_elapsed     — full collection periods before they joined
      is_buy_in_required — False if they joined before the first cycle ended
      display_label      — human-readable string for the join confirmation screen

    Example
    -------
    # Group started 3 weeks ago (weekly, 10k/week). New member joins today.
    # calculate_buy_in_amount(10_000, 7, group_start_ms, joined_ms)
    # -> {"buy_in_amount_ugx": 30_000, "cycles_elapsed": 3, ...}
    """
    now_ms = current_time_ms if current_time_ms is not None else int(
        datetime.now(timezone.utc).timestamp() * 1000
    )

    # Full collection periods completed BEFORE the member joined
    pre_join_elapsed_ms = max(0, member_joined_at_ms - group_start_time_ms)
    pre_join_days = pre_join_elapsed_ms // 86_400_000
    cycles_before_join = int(pre_join_days // collection_frequency_days)

    buy_in_ugx = cycles_before_join * contribution_amount
    is_required = cycles_before_join > 0

    label = (
        f"Buy-in required: {buy_in_ugx:,} UGX (covers {cycles_before_join} missed cycle(s))"
        if is_required
        else "No buy-in required — you are joining before the first cycle ends."
    )

    return {
        "buy_in_amount_ugx": buy_in_ugx,
        "cycles_elapsed": cycles_before_join,
        "is_buy_in_required": is_required,
        "display_label": label,
    }
