"""
rotating_deposit_resolver facade — redirects to app.services.fee_engines.rotating
"""
from app.services.fee_engines.rotating.resolver import (
    resolve_deposit_intent,
    DepositResolution,
    DepositStatus,
    DepositBreakdown,
    PaymentType,
)

__all__ = [
    "resolve_deposit_intent",
    "DepositResolution",
    "DepositStatus",
    "DepositBreakdown",
    "PaymentType",
]
