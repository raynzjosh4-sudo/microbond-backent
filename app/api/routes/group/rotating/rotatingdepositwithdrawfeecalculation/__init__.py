"""
rotatingdepositwithdrawfeecalculation package facade — redirects to app.services.fee_engines.rotating
"""
from app.services.fee_engines.rotating import (
    # Original milestone
    generate_milestone_deposit_schedule,
    get_charge_for_deposit,
    MemberDepositSchedule,
    TARGET_PAYOUT_FEE,
    MTN_FLAT_PAYOUT_FEE,
    MICROBOND_PAYOUT_PROFIT,
    MILESTONE_START,
    MILESTONE_MIDDLE,
    MILESTONE_LAST,
    # Flexible value milestone
    calculate_flexible_rotate_deposit,
    assign_member_value_milestone,
    FlexibleRotateDepositResult,
    # Ledger
    evaluate_member_ledger,
    LedgerStatus,
    LedgerEvaluation,
    # Resolver
    resolve_deposit_intent,
    DepositResolution,
    DepositStatus,
    DepositBreakdown,
    PaymentType,
    # Surplus credit manager
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
    # Original milestone
    "generate_milestone_deposit_schedule",
    "get_charge_for_deposit",
    "MemberDepositSchedule",
    "TARGET_PAYOUT_FEE",
    "MTN_FLAT_PAYOUT_FEE",
    "MICROBOND_PAYOUT_PROFIT",
    "MILESTONE_START",
    "MILESTONE_MIDDLE",
    "MILESTONE_LAST",
    # Flexible value milestone
    "calculate_flexible_rotate_deposit",
    "assign_member_value_milestone",
    "FlexibleRotateDepositResult",
    # Ledger
    "evaluate_member_ledger",
    "LedgerStatus",
    "LedgerEvaluation",
    # Resolver
    "resolve_deposit_intent",
    "DepositResolution",
    "DepositStatus",
    "DepositBreakdown",
    "PaymentType",
    # Surplus credit manager
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
