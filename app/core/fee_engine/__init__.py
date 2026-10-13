"""
fee_engine package
──────────────────────────────────────────────────────────────────────────────
Contains all deposit pricing, fee calculation, and settlement logic
for Microbond's direct MTN MoMo Open API integration.

Quick import:
  from app.core.fee_engine import calculate_deposit_fee, calculate_deposit_fee_preview
  from app.core.fee_engine import DepositFeeBreakdown, MTN_RATE, TIER_TABLE
──────────────────────────────────────────────────────────────────────────────
"""
from .deposit_fee_calculator import (
    calculate_deposit_fee,
    calculate_deposit_fee_preview,
    DepositFeeBreakdown,
    MTN_RATE,
    TIER_TABLE,
)

__all__ = [
    "calculate_deposit_fee",
    "calculate_deposit_fee_preview",
    "DepositFeeBreakdown",
    "MTN_RATE",
    "TIER_TABLE",
]
