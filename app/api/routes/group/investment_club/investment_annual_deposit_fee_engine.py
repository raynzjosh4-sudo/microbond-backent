"""
investment_annual_deposit_fee_engine facade — redirects to app.services.fee_engines.investment_club
"""
from app.services.fee_engines.investment_club import (
    InvestmentDepositCalculation,
    MTN_FLAT_PAYOUT_FEE,
    MICROBOND_PAYOUT_PROFIT,
    TARGET_PAYOUT_FEE,
    DEPOSIT_COUNT_MILESTONES,
    MILESTONE_LABEL,
    assign_member_annual_milestone,
    calculate_investment_group_deposit,
    get_milestone_label,
)

__all__ = [
    "InvestmentDepositCalculation",
    "MTN_FLAT_PAYOUT_FEE",
    "MICROBOND_PAYOUT_PROFIT",
    "TARGET_PAYOUT_FEE",
    "DEPOSIT_COUNT_MILESTONES",
    "MILESTONE_LABEL",
    "assign_member_annual_milestone",
    "calculate_investment_group_deposit",
    "get_milestone_label",
]
