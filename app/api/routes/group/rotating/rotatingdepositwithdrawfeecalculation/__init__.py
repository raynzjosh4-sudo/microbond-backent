"""
rotatingdepositwithdrawfeecalculation package
─────────────────────────────────────────────────────────────────────────────
Rotating group (MERRY_GO_ROUND / ROSCA) complete fee and ledger layer.

Modules
-------
payout_fee_milestone_amortizer    — Original round-index milestone (fixed schedule groups)
rotating_value_milestone_fee_engine — Flexible cumulative-value milestone (lumpsum/catch-up safe)
rotating_ledger_evaluator          — Ledger model: expected vs actual balance
rotating_deposit_resolver          — Full deposit validation + fee computation gateway

Quick imports:
  # Flexible deposit fee (recommended for all production use):
  from app.api.routes.group.rotating.rotatingdepositwithdrawfeecalculation import (
      calculate_flexible_rotate_deposit,
      assign_member_value_milestone,
  )

  # Ledger evaluation (dashboard + reminder engine):
  from app.api.routes.group.rotating.rotatingdepositwithdrawfeecalculation import (
      evaluate_member_ledger,
      LedgerStatus,
  )

  # Full deposit resolution (validation + charge calculation):
  from app.api.routes.group.rotating.rotatingdepositwithdrawfeecalculation import (
      resolve_deposit_intent,
      DepositStatus,
  )
─────────────────────────────────────────────────────────────────────────────
"""

# ── Original round-index milestone (kept for backward compat) ──────────────
from .payout_fee_milestone_amortizer import (
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

# ── Flexible value-threshold milestone (production recommended) ────────────
from .rotating_value_milestone_fee_engine import (
    calculate_flexible_rotate_deposit,
    assign_member_value_milestone,
    FlexibleRotateDepositResult,
)

# ── Ledger evaluator (dashboard + cron reminder engine) ───────────────────
from .rotating_ledger_evaluator import (
    evaluate_member_ledger,
    LedgerStatus,
    LedgerEvaluation,
)

# ── Deposit resolver (full validation gateway) ────────────────────────────
from .rotating_deposit_resolver import (
    resolve_deposit_intent,
    DepositResolution,
    DepositStatus,
    DepositBreakdown,
    PaymentType,
)

# ── Surplus credit & advance manager (waterfall, revaluation, refunds) ─────
from .rotating_surplus_credit_manager import (
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
