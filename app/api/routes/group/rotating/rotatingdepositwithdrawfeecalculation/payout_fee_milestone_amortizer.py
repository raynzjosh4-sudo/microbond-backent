"""
payout_fee_milestone_amortizer facade — redirects to app.services.fee_engines.rotating
"""
from app.services.fee_engines.rotating.amortizer import (
    generate_milestone_deposit_schedule,
    get_charge_for_deposit,
    MemberDepositSchedule,
    TARGET_PAYOUT_FEE,
    MTN_FLAT_PAYOUT_FEE,
    MICROBOND_PAYOUT_PROFIT,
    MILESTONE_START,
    MILESTONE_MIDDLE,
    MILESTONE_LAST,
)

__all__ = [
    "generate_milestone_deposit_schedule",
    "get_charge_for_deposit",
    "MemberDepositSchedule",
    "TARGET_PAYOUT_FEE",
    "MTN_FLAT_PAYOUT_FEE",
    "MICROBOND_PAYOUT_PROFIT",
    "MILESTONE_START",
    "MILESTONE_MIDDLE",
    "MILESTONE_LAST",
]
