"""
target_goal_deposit_fee_engine facade — redirects to app.services.fee_engines.target_savings
"""
from app.services.fee_engines.target_savings import (
    TargetDepositCalculation,
    MTN_FLAT_PAYOUT_FEE,
    MICROBOND_PAYOUT_PROFIT,
    TARGET_PAYOUT_FEE,
    MILESTONE_THRESHOLDS,
    MILESTONE_LABEL,
    assign_member_target_milestone,
    calculate_target_group_deposit,
    get_milestone_label,
)

__all__ = [
    "TargetDepositCalculation",
    "MTN_FLAT_PAYOUT_FEE",
    "MICROBOND_PAYOUT_PROFIT",
    "TARGET_PAYOUT_FEE",
    "MILESTONE_THRESHOLDS",
    "MILESTONE_LABEL",
    "assign_member_target_milestone",
    "calculate_target_group_deposit",
    "get_milestone_label",
]
