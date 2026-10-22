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


def generate_cycle_matrix(
    member_user_ids: list[str],
    group_type: str,
    contribution_minor: int,
    payouts_per_cycle: int = 1,
    reserve_fund_bps: int = 0,
    collection_frequency_days: int = 7,
    start_epoch_seconds: int = 0,
    created_at_epoch_seconds: int = 0,
) -> str:
    """
    Generates cycle obligations and payout schedule with zero float variance.
    """
    if _NATIVE_LOADED and _rust_core is not None:
        return _rust_core.generate_cycle_matrix(
            member_user_ids,
            group_type,
            contribution_minor,
            payouts_per_cycle,
            reserve_fund_bps,
            collection_frequency_days,
            start_epoch_seconds,
            created_at_epoch_seconds,
        )

    if not member_user_ids:
        raise ValueError("Member list cannot be empty")
    if contribution_minor <= 0:
        raise ValueError("Contribution amount must be greater than zero")
    if payouts_per_cycle <= 0:
        raise ValueError("Payouts per cycle must be positive")

    member_count = len(member_user_ids)
    num_cycles = (member_count + payouts_per_cycle - 1) // payouts_per_cycle
    gross_pool = contribution_minor * member_count
    reserve_held = (gross_pool * reserve_fund_bps) // 10_000
    net_payout = max(0, gross_pool - reserve_held)

    seconds_per_interval = collection_frequency_days * 86_400
    obligations = []
    payouts = []

    is_bidding = group_type.upper() == "BIDDING"
    member_idx = 0

    for cycle_idx in range(num_cycles):
        cycle_number = cycle_idx + 1
        due_date = start_epoch_seconds + (cycle_idx * seconds_per_interval)

        for uid in member_user_ids:
            obligations.append({
                "cycle_number": cycle_number,
                "user_id": uid,
                "amount_due": contribution_minor,
                "amount_paid": 0,
                "due_date": due_date,
                "status": "PENDING",
                "created_at": created_at_epoch_seconds,
                "updated_at": created_at_epoch_seconds,
            })

        for _ in range(payouts_per_cycle):
            if is_bidding:
                recipient = None
                p_status = "AUCTION_PENDING"
            elif member_idx < member_count:
                recipient = member_user_ids[member_idx]
                p_status = "PENDING"
                member_idx += 1
            else:
                recipient = None
                p_status = "PENDING"

            payouts.append({
                "cycle_number": cycle_number,
                "user_id": recipient,
                "amount_expected": net_payout,
                "amount_collected": 0,
                "status": p_status,
                "payout_date": due_date,
                "created_at": created_at_epoch_seconds,
                "updated_at": created_at_epoch_seconds,
            })

    return json.dumps({
        "num_cycles": num_cycles,
        "member_count": member_count,
        "gross_pool_minor": gross_pool,
        "reserve_held_minor": reserve_held,
        "net_payout_minor": net_payout,
        "obligations": obligations,
        "payouts": payouts,
    })


def allocate_surplus_waterfall(
    surplus_amount: int,
    current_cycle_number: int,
    standard_contribution: int,
    cycle_overrides_json: str | None = None,
    max_cycles: int | None = None,
) -> str:
    """
    Allocates overpaid deposit across upcoming cycles using chronological FIFO waterfall.
    """
    if _NATIVE_LOADED and _rust_core is not None:
        return _rust_core.allocate_surplus_waterfall(
            surplus_amount,
            current_cycle_number,
            standard_contribution,
            cycle_overrides_json,
            max_cycles,
        )

    if surplus_amount <= 0:
        return json.dumps({
            "total_surplus": 0,
            "cycles_fully_covered_count": 0,
            "fully_covered_cycles": [],
            "partially_covered_cycle": None,
            "unallocated_residual": 0,
            "next_cycle_requiring_payment": current_cycle_number + 1,
            "coverage_details": [],
            "summary_label": "No advance surplus to allocate.",
        })

    overrides = {}
    if cycle_overrides_json and cycle_overrides_json.strip():
        try:
            overrides = {int(k): int(v) for k, v in json.loads(cycle_overrides_json).items()}
        except Exception:
            pass

    remaining = surplus_amount
    target_cycle = current_cycle_number + 1
    fully_covered = []
    partial_cycle = None
    details = []

    while remaining > 0:
        if max_cycles is not None and target_cycle > max_cycles:
            break

        required = overrides.get(target_cycle, standard_contribution)

        if remaining >= required:
            remaining -= required
            fully_covered.append(target_cycle)
            details.append({
                "cycle_number": target_cycle,
                "amount_required": required,
                "amount_allocated": required,
                "shortfall": 0,
                "status": "FULLY_COVERED",
            })
            target_cycle += 1
        else:
            shortfall = required - remaining
            details.append({
                "cycle_number": target_cycle,
                "amount_required": required,
                "amount_allocated": remaining,
                "shortfall": shortfall,
                "status": "PARTIALLY_COVERED",
            })
            partial_cycle = target_cycle
            remaining = 0
            break

    return json.dumps({
        "total_surplus": surplus_amount,
        "cycles_fully_covered_count": len(fully_covered),
        "fully_covered_cycles": fully_covered,
        "partially_covered_cycle": partial_cycle,
        "unallocated_residual": remaining,
        "next_cycle_requiring_payment": target_cycle,
        "coverage_details": details,
        "summary_label": f"Surplus allocated across {len(fully_covered)} cycles.",
    })


def calculate_flexible_rotate_deposit(
    deposit_amount: int,
    current_saved_amount: int,
    assigned_value_milestone: int,
    fee_already_collected: bool = False,
    target_payout_fee: int = 1500,
    mtn_flat_fee: int = 500,
    platform_fee_bps: int = 100,
) -> str:
    """
    Calculates milestone triggered fee amortization and total MTN charge.
    """
    if _NATIVE_LOADED and _rust_core is not None:
        return _rust_core.calculate_flexible_rotate_deposit(
            deposit_amount,
            current_saved_amount,
            assigned_value_milestone,
            fee_already_collected,
            target_payout_fee,
            mtn_flat_fee,
            platform_fee_bps,
        )

    if deposit_amount <= 0:
        raise ValueError("deposit_amount must be positive")
    if assigned_value_milestone <= 0:
        raise ValueError("assigned_value_milestone must be positive")

    platform_fee = (deposit_amount * platform_fee_bps) // 10_000
    base_charge = deposit_amount + mtn_flat_fee + platform_fee
    new_cumulative = current_saved_amount + deposit_amount
    should_trigger = (not fee_already_collected) and (new_cumulative >= assigned_value_milestone)
    payout_fee = target_payout_fee if should_trigger else 0
    final_charge = base_charge + payout_fee

    return json.dumps({
        "deposit_amount": deposit_amount,
        "base_charge_amount": base_charge,
        "mtn_deposit_fee": mtn_flat_fee,
        "microbond_base_fee": platform_fee,
        "hidden_payout_fee": payout_fee,
        "final_charge_amount": final_charge,
        "milestone_triggered_now": should_trigger,
        "new_cumulative_total": new_cumulative,
        "assigned_value_milestone": assigned_value_milestone,
    })

