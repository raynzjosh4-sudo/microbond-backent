"""
Microbond Core Domain Engine.
Delegates to the high-performance compiled Rust binary (microbond_core) when installed,
with an exact, verified reference fallback when developing in environments without C++ toolchains.
"""
import json
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_NATIVE_LOADED = False

try:
    import microbond_core as _rust_core
    if hasattr(_rust_core, "check_join_rules"):
        _NATIVE_LOADED = True
        logger.info("[microbond_core] Successfully loaded authoritative compiled Rust domain engine.")
    else:
        _rust_core = None
        logger.info("[microbond_core] Running with native-identical Python reference engine.")
except ImportError:
    _rust_core = None
    logger.info("[microbond_core] Running with native-identical Python reference engine.")


def is_native_loaded() -> bool:
    """Returns True if the compiled Rust extension is running."""
    return _NATIVE_LOADED


def check_join_rules(
    member_count: int,
    max_members: Optional[int] = None,
    already_member_or_pending: bool = False,
    has_arrears: bool = False,
    trust_score: int = 0,
    minimum_trust_score: Optional[int] = None,
    kyc_tier: int = 0,
    required_kyc_tier: int = 0,
    requires_guarantor: bool = False,
    requires_admin_approval: bool = False,
) -> str:
    """
    Evaluates group join rules deterministically.
    Returns JSON string with status: ACTIVE, PENDING_GUARANTOR, PENDING_APPROVAL, or REJECTED.
    """
    if _NATIVE_LOADED and _rust_core is not None:
        return _rust_core.check_join_rules(
            member_count,
            max_members,
            already_member_or_pending,
            has_arrears,
            trust_score,
            minimum_trust_score,
            kyc_tier,
            required_kyc_tier,
            requires_guarantor,
            requires_admin_approval,
        )

    # Pure reference implementation
    if max_members is not None and member_count >= max_members:
        return json.dumps({
            "status": "REJECTED",
            "reason_code": "GROUP_FULL",
            "reason_message": "Group reached maximum capacity"
        })

    if already_member_or_pending:
        return json.dumps({
            "status": "REJECTED",
            "reason_code": "ALREADY_MEMBER_OR_PENDING",
            "reason_message": "Already in group or pending"
        })

    if has_arrears:
        return json.dumps({
            "status": "REJECTED",
            "reason_code": "ARREARS",
            "reason_message": "Settle missed payments first"
        })

    if minimum_trust_score is not None and trust_score < minimum_trust_score:
        return json.dumps({
            "status": "REJECTED",
            "reason_code": "TRUST_SCORE",
            "reason_message": "Trust score is below the group requirement"
        })

    if kyc_tier < required_kyc_tier:
        return json.dumps({
            "status": "REJECTED",
            "reason_code": "KYC_TIER",
            "reason_message": "Complete the required KYC tier"
        })

    if requires_guarantor:
        status = "PENDING_GUARANTOR"
    elif requires_admin_approval:
        status = "PENDING_APPROVAL"
    else:
        status = "ACTIVE"

    return json.dumps({
        "status": status,
        "reason_code": None,
        "reason_message": None
    })


def calculate_rotating_payout(
    contribution_minor: int,
    member_count: int,
    late_days: int = 0,
    grace_period_days: int = 0,
    late_fee_minor: int = 0,
) -> str:
    """
    Computes rotating group pooled payout and penalties in minor units (UGX cents).
    Guarantees no floating-point variance and protects against overflow.
    """
    if _NATIVE_LOADED and _rust_core is not None:
        return _rust_core.calculate_rotating_payout(
            contribution_minor,
            member_count,
            late_days,
            grace_period_days,
            late_fee_minor,
        )

    if contribution_minor <= 0:
        raise ValueError("Contribution amount must be greater than zero")
    if member_count <= 0:
        raise ValueError("Member count must be greater than zero")

    payout_minor = contribution_minor * member_count
    penalty_minor = late_fee_minor if late_days > grace_period_days else 0
    penalty_minor = max(0, penalty_minor)
    net_payout_minor = max(0, payout_minor - penalty_minor)

    return json.dumps({
        "payout_minor": payout_minor,
        "penalty_minor": penalty_minor,
        "net_payout_minor": net_payout_minor,
        "currency": "UGX"
    })


def calculate_penalty(
    amount_minor: int,
    late_days: int,
    grace_period_days: int = 0,
    penalty_fixed_minor: int = 0,
    penalty_daily_rate_bps: int = 0,
) -> str:
    """
    Calculates late penalty in minor currency units based on grace period and daily rate.
    """
    if _NATIVE_LOADED and _rust_core is not None:
        return _rust_core.calculate_penalty(
            amount_minor,
            late_days,
            grace_period_days,
            penalty_fixed_minor,
            penalty_daily_rate_bps,
        )

    if late_days <= grace_period_days:
        return json.dumps({
            "penalty_minor": 0,
            "is_late": False,
            "late_days": max(0, late_days),
            "currency": "UGX"
        })

    overdue_days = late_days - grace_period_days
    daily_rate = (amount_minor * penalty_daily_rate_bps) // 10_000
    variable_penalty = daily_rate * overdue_days
    total_penalty = max(0, penalty_fixed_minor + variable_penalty)

    return json.dumps({
        "penalty_minor": total_penalty,
        "is_late": True,
        "late_days": late_days,
        "currency": "UGX"
    })


def canonical_audit_hash(previous_hash: str, event_json: str) -> str:
    """
    Computes canonical SHA-256 hash chaining previous event hash and current event JSON.
    """
    if _NATIVE_LOADED and _rust_core is not None:
        return _rust_core.canonical_audit_hash(previous_hash, event_json)

    hasher = hashlib.sha256()
    hasher.update(previous_hash.encode("utf-8"))
    hasher.update(b":")
    hasher.update(event_json.encode("utf-8"))
    return hasher.hexdigest()
