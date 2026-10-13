"""
rotating_surplus_credit_manager facade — redirects to app.services.fee_engines.rotating
"""
from app.services.fee_engines.rotating.surplus import (
    allocate_surplus_to_future_cycles,
    recalculate_credit_on_contribution_change,
    format_deposit_broadcast_message,
    validate_surplus_withdrawal,
    CoverageStatus,
    CycleCoverageDetail,
    SurplusAllocationResult,
    ContributionAdjustmentResult,
    WithdrawalEligibilityStatus,
    SurplusWithdrawalEvaluation,
)

__all__ = [
    "allocate_surplus_to_future_cycles",
    "recalculate_credit_on_contribution_change",
    "format_deposit_broadcast_message",
    "validate_surplus_withdrawal",
    "CoverageStatus",
    "CycleCoverageDetail",
    "SurplusAllocationResult",
    "ContributionAdjustmentResult",
    "WithdrawalEligibilityStatus",
    "SurplusWithdrawalEvaluation",
]
