"""
deposit_fee_calculator.py
─────────────────────────────────────────────────────────────────────────────
Microbond Deposit Fee Engine — Direct MTN MoMo Open API Integration

STRATEGY: Psychological Precise Pricing
  Instead of rounding platform fees to clean numbers (which look like a
  deliberate "tax"), we set the platform fee to exactly (MTN_FEE - N) where N
  is a small incrementing offset per deposit tier. The resulting total fee
  (e.g. 14,979 UGX instead of 15,000 UGX) reads to the user as a precise
  system calculation — not a profit margin — dramatically reducing friction.

HOW THE MATH WORKS:
  1. User wants to deposit `group_target_amount` into their savings group.
  2. MTN charges 1.5% on the total amount collected.
  3. We calculate: mtn_fee = round(group_target_amount * 1.5%)
  4. We set:       platform_fee = mtn_fee - psychological_offset
  5. Total fee:    total_fee = mtn_fee + platform_fee
  6. Charged:      charge_amount = group_target_amount + total_fee
  7. Settlement:   MTN deducts their 1.5% from charge_amount.
                   Microbond escrow receives the remainder.
                   group_target_amount is credited to the user's savings pool.
                   platform_fee is retained as Microbond revenue.

USAGE:
  from app.core.fee_engine import calculate_deposit_fee

  breakdown = calculate_deposit_fee(50_000)
  # breakdown.charge_amount  ->  51482
  # breakdown.platform_fee   ->  732
  # breakdown.mtn_fee        ->  750
─────────────────────────────────────────────────────────────────────────────
"""

from dataclasses import dataclass
from typing import Optional


# ── Constants ──────────────────────────────────────────────────────────────

# MTN MoMo Open API collection fee rate (1.5%)
MTN_RATE: float = 0.015

# Psychological offset tier table.
# Each row defines an upper boundary (exclusive) for the group_target_amount
# and the integer to subtract from the raw MTN fee to derive the platform fee.
# Tiers are matched top-down; the first row whose max_ugx exceeds the deposit wins.
#
# Tier design (from spec):
#   <=   5,000 UGX  -> offset 15 -> platform =     75 - 15  =     60 UGX
#   <=  10,000 UGX  -> offset 16 -> platform =    150 - 16  =    134 UGX
#   <=  20,000 UGX  -> offset 17 -> platform =    300 - 17  =    283 UGX
#   <=  50,000 UGX  -> offset 18 -> platform =    750 - 18  =    732 UGX
#   <= 100,000 UGX  -> offset 19 -> platform =  1,500 - 19  =  1,481 UGX
#   <= 500,000 UGX  -> offset 21 -> platform =  7,500 - 21  =  7,479 UGX (skip 20)
#   >  500,000 UGX  -> offset 22 -> platform = 15,000 - 22  = 14,978 UGX
#
# Format: (max_ugx_exclusive, psychological_offset)
# None for max_ugx_exclusive means "all amounts above the previous tier".
TIER_TABLE: list = [
    (5_001,   15),  # <= 5,000 UGX
    (10_001,  16),  # <= 10,000 UGX
    (20_001,  17),  # <= 20,000 UGX
    (50_001,  18),  # <= 50,000 UGX
    (100_001, 19),  # <= 100,000 UGX
    (500_001, 21),  # <= 500,000 UGX  (intentional skip of 20 per spec)
    (None,    22),  # >  500,000 UGX
]


# ── Data Model ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DepositFeeBreakdown:
    """
    Immutable result object returned by `calculate_deposit_fee`.

    Attributes
    ----------
    group_target_amount : int
        The exact UGX amount credited to the user's savings pool.
    mtn_fee : int
        MTN's collection fee (1.5% of group_target_amount, rounded).
    platform_fee : int
        Microbond's revenue = mtn_fee - psychological_offset.
    total_fee : int
        Combined processing cost shown to the user (mtn_fee + platform_fee).
    charge_amount : int
        The exact figure passed to MTN RequestToPay — what the user sees
        and approves on their phone's MoMo PIN screen.
    psychological_offset : int
        Tier-specific integer subtracted from the raw MTN fee to create the
        irregular, "precise-looking" platform fee.
    microbond_net_revenue : int
        Revenue Microbond retains after MTN has taken their 1.5% cut.
        Equals platform_fee exactly.
    """
    group_target_amount: int
    mtn_fee: int
    platform_fee: int
    total_fee: int
    charge_amount: int
    psychological_offset: int
    microbond_net_revenue: int


# ── Internal Helpers ───────────────────────────────────────────────────────

def _get_psychological_offset(group_target_amount: int) -> int:
    """
    Look up the psychological offset for a given deposit amount.
    Matches the first tier whose upper boundary exceeds the deposit.
    """
    for max_ugx, offset in TIER_TABLE:
        if max_ugx is None or group_target_amount < max_ugx:
            return offset
    # Fallback — should never reach here given None-terminated TIER_TABLE
    return TIER_TABLE[-1][1]


# ── Public API ─────────────────────────────────────────────────────────────

def calculate_deposit_fee(group_target_amount: int) -> DepositFeeBreakdown:
    """
    Calculate the complete deposit fee breakdown for a Microbond savings
    group deposit using the psychological pricing strategy.

    Parameters
    ----------
    group_target_amount : int
        The exact UGX amount the user wants credited to their savings pool.
        Must be a positive integer (whole UGX, no fractions).

    Returns
    -------
    DepositFeeBreakdown
        Frozen dataclass with all fee components and the final charge
        amount to pass to the MTN MoMo RequestToPay API.

    Raises
    ------
    ValueError
        If `group_target_amount` is not a positive integer.

    Examples
    --------
    >>> from app.core.fee_engine import calculate_deposit_fee
    >>> b = calculate_deposit_fee(50_000)
    >>> b.charge_amount
    51482
    >>> b.mtn_fee
    750
    >>> b.platform_fee
    732
    >>> b.microbond_net_revenue
    732
    """
    if not isinstance(group_target_amount, int) or group_target_amount <= 0:
        raise ValueError(
            f"group_target_amount must be a positive integer (UGX). "
            f"Got: {group_target_amount!r}"
        )

    offset = _get_psychological_offset(group_target_amount)

    # MTN's 1.5% fee — calculated on the base deposit amount, rounded to UGX
    mtn_fee: int = round(group_target_amount * MTN_RATE)

    # Platform fee: the psychological irregular number.
    # Clamped to 0 to guard against tiny deposits where offset > mtn_fee.
    platform_fee: int = max(0, mtn_fee - offset)

    total_fee: int = mtn_fee + platform_fee
    charge_amount: int = group_target_amount + total_fee

    # Net Microbond revenue after MTN deducts their 1.5% from charge_amount.
    # Equals platform_fee because the two 1.5% slices cancel perfectly.
    microbond_net_revenue: int = platform_fee

    return DepositFeeBreakdown(
        group_target_amount=group_target_amount,
        mtn_fee=mtn_fee,
        platform_fee=platform_fee,
        total_fee=total_fee,
        charge_amount=charge_amount,
        psychological_offset=offset,
        microbond_net_revenue=microbond_net_revenue,
    )


def calculate_deposit_fee_preview(group_target_amount: int) -> dict:
    """
    Return a JSON-serializable dict of the fee breakdown, ready to send
    to the mobile client as a deposit confirmation preview payload.

    Parameters
    ----------
    group_target_amount : int
        The base deposit amount in UGX.

    Returns
    -------
    dict
        Keys:
          group_target_amount  — what lands in the user's savings pool
          mtn_fee              — MTN's cut
          platform_fee         — Microbond's revenue
          total_fee            — total processing cost
          charge_amount        — exact amount shown on the MoMo PIN prompt
          display_label        — human-readable string for the UI button
    """
    b = calculate_deposit_fee(group_target_amount)
    return {
        "group_target_amount": b.group_target_amount,
        "mtn_fee": b.mtn_fee,
        "platform_fee": b.platform_fee,
        "total_fee": b.total_fee,
        "charge_amount": b.charge_amount,
        "display_label": f"{b.charge_amount:,} UGX",
    }
