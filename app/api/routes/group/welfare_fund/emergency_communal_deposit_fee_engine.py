"""
emergency_communal_deposit_fee_engine.py
─────────────────────────────────────────────────────────────────────────────
Emergency / Welfare / Social Fund (Munno Mukabi) — Deposit Fee Engine

CONTEXT:
  A Welfare Fund is a communal safety net. Members make small, regular
  deposits (e.g., 5,000 UGX weekly) and the pool sits idle until a member
  suffers a crisis — medical emergency, accident, or funeral — at which point
  the group votes to disburse funds to the member in need.

  Key traits that make this group type unique:
    • No fixed savings cycles or round schedules.
    • No target goal amount.
    • Payouts are RARE and entirely UNPREDICTABLE (cannot pre-schedule).
    • Crisis payout UX is sacred — deducting any fee from an emergency
      payment is morally unacceptable and destroys trust instantly.

THE PROBLEM:
  The milestone strategies used for other group types cannot work here:
    • Round-index milestones (Rotate) — no fixed rounds.
    • Progress-percentage milestones (Target) — no savings goal.
    • Annual deposit-count milestones (Investment) — would over-collect
      if few emergencies occur and under-collect if many do.

STRATEGY: The Communal Recovery Queue (Next-in-Line Absorption)
  This strategy perfectly matches 1 fee recovery to 1 payout event — never
  more, never less.

  HOW IT WORKS:
    1. Emergency strikes → group votes → payout approved.
    2. Microbond sends the FULL requested amount to the member in crisis.
       (e.g. exactly 200,000 UGX. Zero deductions. Member in crisis is safe.)
    3. The database column `group.pending_payout_fees_count` increments by 1.
    4. The next member who opens the app to make their routine deposit
       silently absorbs the 979 UGX payout fee into their charge.
    5. `pending_payout_fees_count` decrements back to 0.

  MULTIPLE EMERGENCIES:
    If 2 emergencies happen before anyone deposits:
      • pending_payout_fees_count = 2.
      • The next depositor absorbs 2 × 979 = 1,958 UGX.
    This handles bursts cleanly without leaving Microbond out of pocket.

  WHY THIS WORKS PSYCHOLOGICALLY:
    • The depositing member sees a slightly higher-than-usual number
      (e.g. 6,114 UGX instead of 5,135 UGX for a 5,000 UGX deposit).
      This reads as a routine network fluctuation — not a fee.
    • The member in crisis sees an exact, uncut payout and trusts
      Microbond with their life.
    • The cost is communal: the group bears the network fee together,
      organically rotating across whoever deposits next.

USAGE:
  # On every routine welfare deposit:
  from app.api.routes.group.welfare_fund.emergency_communal_deposit_fee_engine import (
      calculate_emergency_group_deposit,
  )

  result = calculate_emergency_group_deposit(
      deposit_amount=5_000,
      group_pending_payout_fees_count=group.pending_payout_fees_count,
  )
  # Pass result.final_charge_amount to MTN RequestToPay.
  # If result.cleared_pending_fee:
  #   group.pending_payout_fees_count = max(0, pending - result.fees_cleared)
  #   session.commit()

  # When an emergency payout is approved and sent:
  from app.api.routes.group.welfare_fund.emergency_communal_deposit_fee_engine import (
      register_emergency_payout,
  )
  new_count = register_emergency_payout(current_pending=group.pending_payout_fees_count)
  group.pending_payout_fees_count = new_count  # persist to DB
─────────────────────────────────────────────────────────────────────────────
"""

from dataclasses import dataclass

from app.core.fee_engine import calculate_deposit_fee, DepositFeeBreakdown


# ── Constants ──────────────────────────────────────────────────────────────

# MTN MoMo flat fee charged per emergency disbursement
MTN_FLAT_PAYOUT_FEE: int = 300  # UGX

# Microbond platform profit per disbursement event
MICROBOND_PAYOUT_PROFIT: int = 679  # UGX

# Total cost recovered per emergency payout event
TARGET_PAYOUT_FEE: int = MTN_FLAT_PAYOUT_FEE + MICROBOND_PAYOUT_PROFIT  # 979 UGX


# ── Data Model ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class EmergencyDepositCalculation:
    """
    Immutable result of a single deposit calculation for an Emergency /
    Welfare Fund group.

    Attributes
    ----------
    deposit_amount : int
        The raw UGX amount the member intends to contribute this session.
    base_charge_amount : int
        Standard charge (deposit + MTN 1.5% + Microbond psychological fee),
        before any pending payout fee absorption.
    mtn_deposit_fee : int
        MTN's 1.5% collection fee on the deposit amount.
    microbond_deposit_fee : int
        Microbond's psychological base platform fee.
    hidden_payout_fee : int
        The total UGX absorbed from the pending fee queue this deposit.
        = fees_cleared × TARGET_PAYOUT_FEE (979 UGX each).
        0 if the queue was empty.
    final_charge_amount : int
        Exact figure sent to MTN RequestToPay — what appears on the
        member's MoMo PIN prompt.
    cleared_pending_fee : bool
        True if at least one pending payout fee was absorbed this deposit.
        Use this flag to trigger the queue decrement in the DB.
    fees_cleared : int
        Exact number of pending payout fees absorbed by this single deposit.
        Decrement `group.pending_payout_fees_count` by this amount.
    """
    deposit_amount: int
    base_charge_amount: int
    mtn_deposit_fee: int
    microbond_deposit_fee: int
    hidden_payout_fee: int
    final_charge_amount: int
    cleared_pending_fee: bool
    fees_cleared: int

    def to_dict(self) -> dict:
        """JSON-serializable representation for API response / audit logging."""
        return {
            "deposit_amount": self.deposit_amount,
            "base_charge_amount": self.base_charge_amount,
            "mtn_deposit_fee": self.mtn_deposit_fee,
            "microbond_deposit_fee": self.microbond_deposit_fee,
            "hidden_payout_fee": self.hidden_payout_fee,
            "final_charge_amount": self.final_charge_amount,
            "cleared_pending_fee": self.cleared_pending_fee,
            "fees_cleared": self.fees_cleared,
        }


# ── Public API ─────────────────────────────────────────────────────────────

def calculate_emergency_group_deposit(
    deposit_amount: int,
    group_pending_payout_fees_count: int,
) -> EmergencyDepositCalculation:
    """
    Calculate the exact MTN RequestToPay charge for a routine welfare deposit.

    If the group has any pending payout fees queued from recent emergency
    disbursements, this deposit silently absorbs ALL of them in a single
    charge. The queue is cleared in full — not one at a time — to avoid
    spreading micro-additions across multiple future depositors.

    Parameters
    ----------
    deposit_amount : int
        The UGX amount the member is depositing right now. Must be positive.
    group_pending_payout_fees_count : int
        The current number of outstanding unrecovered payout fees for this
        group. Read directly from `group.pending_payout_fees_count` in the DB.
        0 means no emergencies have occurred since the last recovery.

    Returns
    -------
    EmergencyDepositCalculation
        Contains final_charge_amount for MTN RequestToPay.
        If cleared_pending_fee is True, decrement the DB queue by fees_cleared.

    Raises
    ------
    ValueError
        If deposit_amount is not a positive integer or
        group_pending_payout_fees_count is negative.

    Examples
    --------
    >>> # Normal week — no pending fees
    >>> r = calculate_emergency_group_deposit(5_000, 0)
    >>> r.final_charge_amount
    5135
    >>> r.cleared_pending_fee
    False

    >>> # One emergency payout was just sent — queue = 1
    >>> r = calculate_emergency_group_deposit(5_000, 1)
    >>> r.final_charge_amount   # 5,135 + 979 = 6,114
    6114
    >>> r.cleared_pending_fee
    True
    >>> r.fees_cleared
    1

    >>> # Two emergencies hit before anyone deposited — queue = 2
    >>> r = calculate_emergency_group_deposit(5_000, 2)
    >>> r.final_charge_amount   # 5,135 + (2 × 979) = 7,093
    7093
    >>> r.fees_cleared
    2
    """
    if not isinstance(deposit_amount, int) or deposit_amount <= 0:
        raise ValueError(f"deposit_amount must be a positive int. Got: {deposit_amount!r}")
    if not isinstance(group_pending_payout_fees_count, int) or group_pending_payout_fees_count < 0:
        raise ValueError(
            f"group_pending_payout_fees_count must be a non-negative int. "
            f"Got: {group_pending_payout_fees_count!r}"
        )

    # ── Base psychological deposit fees ────────────────────────────────────
    base: DepositFeeBreakdown = calculate_deposit_fee(deposit_amount)

    # ── Queue absorption ───────────────────────────────────────────────────
    # Absorb ALL pending fees in one deposit — clears the queue completely.
    fees_to_clear: int = group_pending_payout_fees_count
    total_payout_fee: int = fees_to_clear * TARGET_PAYOUT_FEE
    final_charge: int = base.charge_amount + total_payout_fee

    return EmergencyDepositCalculation(
        deposit_amount=deposit_amount,
        base_charge_amount=base.charge_amount,
        mtn_deposit_fee=base.mtn_fee,
        microbond_deposit_fee=base.platform_fee,
        hidden_payout_fee=total_payout_fee,
        final_charge_amount=final_charge,
        cleared_pending_fee=fees_to_clear > 0,
        fees_cleared=fees_to_clear,
    )


def register_emergency_payout(current_pending: int) -> int:
    """
    Called immediately after an emergency disbursement is successfully sent
    to a member in crisis. Increments the group-level pending fee queue.

    This is the ONLY place the queue counter is ever increased. Call this
    after the MTN Disbursement API confirms the payout succeeded — never
    before, to avoid queue drift on failed payments.

    Parameters
    ----------
    current_pending : int
        The group's current `pending_payout_fees_count` value from the DB.

    Returns
    -------
    int
        The new value to write back to `group.pending_payout_fees_count`.

    Example
    -------
    >>> register_emergency_payout(0)
    1
    >>> register_emergency_payout(1)   # second emergency before recovery
    2
    """
    if not isinstance(current_pending, int) or current_pending < 0:
        raise ValueError(f"current_pending must be a non-negative int. Got: {current_pending!r}")
    return current_pending + 1


def get_new_pending_count_after_deposit(current_pending: int, fees_cleared: int) -> int:
    """
    Helper to safely compute the new pending count after a deposit absorbs
    fees. Clamps to 0 to prevent negative values from race conditions.

    Parameters
    ----------
    current_pending : int
        The group's pending_payout_fees_count read before the deposit.
    fees_cleared : int
        The fees_cleared value from EmergencyDepositCalculation.

    Returns
    -------
    int
        New value to write to group.pending_payout_fees_count.
    """
    return max(0, current_pending - fees_cleared)
