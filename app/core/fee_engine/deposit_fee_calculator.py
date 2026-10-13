"""
deposit_fee_calculator facade — redirects to app.services.fee_engines.base_deposit_fee
"""
from app.services.fee_engines.base_deposit_fee import (
    DepositFeeBreakdown,
    MTN_RATE,
    TIER_TABLE,
    calculate_deposit_fee,
    calculate_deposit_fee_preview,
)
from app.services.fee_engines.base_deposit_fee.helpers.get_psychological_offset import (
    get_psychological_offset as _get_psychological_offset,
)

__all__ = [
    "DepositFeeBreakdown",
    "MTN_RATE",
    "TIER_TABLE",
    "calculate_deposit_fee",
    "calculate_deposit_fee_preview",
    "_get_psychological_offset",
]
