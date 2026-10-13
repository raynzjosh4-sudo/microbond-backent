"""
emergency_communal_deposit_fee_engine facade — redirects to app.services.fee_engines.welfare_fund
"""
from app.services.fee_engines.welfare_fund import (
    EmergencyDepositCalculation,
    MTN_FLAT_PAYOUT_FEE,
    MICROBOND_PAYOUT_PROFIT,
    TARGET_PAYOUT_FEE,
    calculate_emergency_group_deposit,
    register_emergency_payout,
    get_new_pending_count_after_deposit,
)

__all__ = [
    "EmergencyDepositCalculation",
    "MTN_FLAT_PAYOUT_FEE",
    "MICROBOND_PAYOUT_PROFIT",
    "TARGET_PAYOUT_FEE",
    "calculate_emergency_group_deposit",
    "register_emergency_payout",
    "get_new_pending_count_after_deposit",
]
