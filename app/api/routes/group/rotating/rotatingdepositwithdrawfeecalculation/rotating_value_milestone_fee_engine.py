"""
rotating_value_milestone_fee_engine facade — redirects to app.services.fee_engines.rotating
"""
from app.services.fee_engines.rotating.amortizer import (
    calculate_flexible_rotate_deposit,
    assign_member_value_milestone,
    get_milestone_label,
    FlexibleRotateDepositResult,
    TARGET_PAYOUT_FEE,
    MTN_FLAT_PAYOUT_FEE,
    MICROBOND_PAYOUT_PROFIT,
    MILESTONE_PERCENTAGES,
    MILESTONE_LABEL,
)

__all__ = [
    "calculate_flexible_rotate_deposit",
    "assign_member_value_milestone",
    "get_milestone_label",
    "FlexibleRotateDepositResult",
    "TARGET_PAYOUT_FEE",
    "MTN_FLAT_PAYOUT_FEE",
    "MICROBOND_PAYOUT_PROFIT",
    "MILESTONE_PERCENTAGES",
    "MILESTONE_LABEL",
]
