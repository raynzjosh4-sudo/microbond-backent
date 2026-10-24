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
    cycle_overrides_json: str | dict | None = None,
    max_cycles: int | None = None,
    cycle_overrides: dict | str | None = None,
) -> str:
    """
    Allocates overpaid deposit across upcoming cycles using chronological FIFO waterfall.
    """
    overrides_val = cycle_overrides if cycle_overrides is not None else cycle_overrides_json
    if isinstance(overrides_val, dict):
        cycle_overrides_json_str = json.dumps({str(k): v for k, v in overrides_val.items()})
        overrides = {int(k): int(v) for k, v in overrides_val.items()}
    elif isinstance(overrides_val, str) and overrides_val.strip():
        cycle_overrides_json_str = overrides_val
        try:
            overrides = {int(k): int(v) for k, v in json.loads(overrides_val).items()}
        except Exception:
            overrides = {}
    else:
        cycle_overrides_json_str = None
        overrides = {}

    if _NATIVE_LOADED and _rust_core is not None:
        return _rust_core.allocate_surplus_waterfall(
            surplus_amount,
            current_cycle_number,
            standard_contribution,
            cycle_overrides_json_str,
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


def detect_guarantor_cycle(
    existing_edges: list[tuple[str, str]],
    new_guarantor: str,
    new_borrower: str,
) -> bool:
    """
    Detects if adding a directed vouching edge (new_guarantor -> new_borrower)
    creates a cyclic dependency in the vouching graph.
    """
    if _NATIVE_LOADED and _rust_core is not None:
        return bool(_rust_core.detect_guarantor_cycle(existing_edges, new_guarantor, new_borrower))

    if new_guarantor == new_borrower:
        return True

    adj: dict[str, list[str]] = {}
    for g, b in existing_edges:
        adj.setdefault(g, []).append(b)

    from collections import deque
    queue = deque([new_borrower])
    visited = {new_borrower}

    while queue:
        curr = queue.popleft()
        if curr == new_guarantor:
            return True
        for nxt in adj.get(curr, []):
            if nxt not in visited:
                visited.add(nxt)
                queue.append(nxt)

    return False


def evaluate_cross_group_exposure(
    user_active_rotating_groups: int,
    max_allowed_rotating: int = 10,
    has_unpaid_hit_and_run: bool = False,
    late_obligations_count: int = 0,
    historical_penalties: int = 0,
    max_historical_penalties: int = 3,
    user_trust_score: int = 50,
    min_trust_score: int | None = None,
    user_kyc_tier: int = 1,
    min_kyc_tier: int = 1,
    is_payout_order_locked: bool = False,
) -> str:
    """
    Evaluates multi-group cross exposure and anti-fraud rules.
    """
    if _NATIVE_LOADED and _rust_core is not None:
        return _rust_core.evaluate_cross_group_exposure(
            user_active_rotating_groups,
            max_allowed_rotating,
            has_unpaid_hit_and_run,
            late_obligations_count,
            historical_penalties,
            max_historical_penalties,
            user_trust_score,
            min_trust_score,
            user_kyc_tier,
            min_kyc_tier,
            is_payout_order_locked,
        )

    if is_payout_order_locked:
        return json.dumps({
            "is_eligible": False,
            "risk_tier": "REJECTED_CYCLE_LOCKED",
            "rejection_reason": "The payout cycle has already started. You cannot join mid-way.",
        })

    if user_active_rotating_groups >= max_allowed_rotating:
        return json.dumps({
            "is_eligible": False,
            "risk_tier": "REJECTED_OVER_CAPACITY",
            "rejection_reason": f"You are already in {user_active_rotating_groups} active rotating groups. Maximum allowed is {max_allowed_rotating}.",
        })

    if has_unpaid_hit_and_run:
        return json.dumps({
            "is_eligible": False,
            "risk_tier": "REJECTED_HIT_AND_RUN",
            "rejection_reason": "You have received a payout in another group but still owe contributions to that cycle.",
        })

    if late_obligations_count > 0:
        return json.dumps({
            "is_eligible": False,
            "risk_tier": "REJECTED_ARREARS",
            "rejection_reason": "You currently have an unpaid missed payment or arrears in another group.",
        })

    if historical_penalties >= max_historical_penalties:
        return json.dumps({
            "is_eligible": False,
            "risk_tier": "REJECTED_PENALTIES",
            "rejection_reason": f"Your account has a history of slow payments ({historical_penalties} penalties). You are restricted from joining new groups.",
        })

    if min_trust_score is not None and user_trust_score < min_trust_score:
        return json.dumps({
            "is_eligible": False,
            "risk_tier": "REJECTED_TRUST_SCORE",
            "rejection_reason": f"Your Trust Score ({user_trust_score}) is below the required {min_trust_score}.",
        })

    if user_kyc_tier < min_kyc_tier:
        return json.dumps({
            "is_eligible": False,
            "risk_tier": "REJECTED_KYC",
            "rejection_reason": f"You need KYC Tier {min_kyc_tier} to join this group. Current tier: {user_kyc_tier}.",
        })

    return json.dumps({
        "is_eligible": True,
        "risk_tier": "APPROVED",
        "rejection_reason": None,
    })


def evaluate_guarantor_capacity(
    guarantor_trust_score: int,
    total_contributed_minor: int,
    current_active_liability_minor: int,
    new_pledge_minor: int,
    bad_obligations_count: int = 0,
    min_guarantor_trust_score: int = 70,
    base_allowance_minor: int = 500_000,
) -> str:
    """
    Evaluates dynamic guarantor risk capacity based on trust score and contribution history.
    """
    if _NATIVE_LOADED and _rust_core is not None:
        return _rust_core.evaluate_guarantor_capacity(
            guarantor_trust_score,
            total_contributed_minor,
            current_active_liability_minor,
            new_pledge_minor,
            bad_obligations_count,
            min_guarantor_trust_score,
            base_allowance_minor,
        )

    if bad_obligations_count > 0:
        return json.dumps({
            "is_approved": False,
            "dynamic_max_liability_minor": 0,
            "total_projected_liability_minor": current_active_liability_minor + new_pledge_minor,
            "remaining_capacity_minor": 0,
            "rejection_reason": "Guarantor currently has overdue or defaulted payments and cannot take on risk.",
        })

    if guarantor_trust_score < min_guarantor_trust_score:
        return json.dumps({
            "is_approved": False,
            "dynamic_max_liability_minor": 0,
            "total_projected_liability_minor": current_active_liability_minor + new_pledge_minor,
            "remaining_capacity_minor": 0,
            "rejection_reason": f"Guarantor has a Trust Score of {guarantor_trust_score}. A minimum of {min_guarantor_trust_score} is required to vouch for others.",
        })

    historical_weight = (total_contributed_minor * 5 * guarantor_trust_score) // 100
    dynamic_max_liability = max(base_allowance_minor, historical_weight)
    total_projected = current_active_liability_minor + new_pledge_minor

    if total_projected > dynamic_max_liability:
        return json.dumps({
            "is_approved": False,
            "dynamic_max_liability_minor": dynamic_max_liability,
            "total_projected_liability_minor": total_projected,
            "remaining_capacity_minor": 0,
            "rejection_reason": f"Guarantor is over-leveraged. Dynamic risk capacity is {dynamic_max_liability} UGX, projected liability is {total_projected} UGX.",
        })

    remaining = max(0, dynamic_max_liability - total_projected)
    return json.dumps({
        "is_approved": True,
        "dynamic_max_liability_minor": dynamic_max_liability,
        "total_projected_liability_minor": total_projected,
        "remaining_capacity_minor": remaining,
        "rejection_reason": None,
    })


def evaluate_escrow_release(
    timelock_expired: bool,
    milestones_total: int = 0,
    milestones_completed: int = 0,
    signers_required: int = 0,
    signatures_collected: int = 0,
    dispute_active: bool = False,
    rule_mode: str = "ALL_CONDITIONS",
) -> str:
    """
    Formally evaluates release predicates for funds held in escrow.
    """
    if _NATIVE_LOADED and _rust_core is not None:
        return _rust_core.evaluate_escrow_release(
            timelock_expired,
            milestones_total,
            milestones_completed,
            signers_required,
            signatures_collected,
            dispute_active,
            rule_mode,
        )

    if dispute_active:
        return json.dumps({
            "release_permitted": False,
            "status": "DISPUTED",
            "rejection_reason": "Escrow payout is locked due to an active dispute or arbitration filing.",
        })

    milestones_met = milestones_total <= 0 or milestones_completed >= milestones_total
    consensus_met = signers_required <= 0 or signatures_collected >= signers_required
    mode = rule_mode.upper()

    if mode == "TIMELOCK_ONLY":
        if timelock_expired:
            return json.dumps({"release_permitted": True, "status": "PERMITTED", "rejection_reason": None})
        else:
            return json.dumps({"release_permitted": False, "status": "LOCKED_TIMELOCK", "rejection_reason": "Timelock has not expired yet."})

    elif mode == "CONSENSUS_ONLY":
        if consensus_met:
            return json.dumps({"release_permitted": True, "status": "PERMITTED", "rejection_reason": None})
        else:
            return json.dumps({
                "release_permitted": False,
                "status": "LOCKED_SIGNATURES",
                "rejection_reason": f"Insufficient signatures. Required: {signers_required}, Collected: {signatures_collected}.",
            })

    elif mode == "MILESTONE_AND_CONSENSUS":
        if not milestones_met:
            return json.dumps({
                "release_permitted": False,
                "status": "LOCKED_MILESTONES",
                "rejection_reason": f"Milestones incomplete. Required: {milestones_total}, Completed: {milestones_completed}.",
            })
        if not consensus_met:
            return json.dumps({
                "release_permitted": False,
                "status": "LOCKED_SIGNATURES",
                "rejection_reason": f"Quorum not reached. Required signers: {signers_required}, Collected: {signatures_collected}.",
            })
        return json.dumps({"release_permitted": True, "status": "PERMITTED", "rejection_reason": None})

    elif mode == "TIMELOCK_OR_CONSENSUS":
        if timelock_expired or consensus_met:
            return json.dumps({"release_permitted": True, "status": "PERMITTED", "rejection_reason": None})
        else:
            return json.dumps({
                "release_permitted": False,
                "status": "LOCKED_TIMELOCK_OR_CONSENSUS",
                "rejection_reason": "Neither the timelock expiration nor the signature threshold has been satisfied.",
            })

    else:  # "ALL_CONDITIONS" default
        if not timelock_expired:
            return json.dumps({"release_permitted": False, "status": "LOCKED_TIMELOCK", "rejection_reason": "Timelock period is still active."})
        if not milestones_met:
            return json.dumps({
                "release_permitted": False,
                "status": "LOCKED_MILESTONES",
                "rejection_reason": f"All milestones must be verified prior to release. {milestones_completed}/{milestones_total} verified.",
            })
        if not consensus_met:
            return json.dumps({
                "release_permitted": False,
                "status": "LOCKED_SIGNATURES",
                "rejection_reason": f"Multi-sig approval quorum required. {signatures_collected}/{signers_required} signed.",
            })
        return json.dumps({"release_permitted": True, "status": "PERMITTED", "rejection_reason": None})


def calculate_decayed_quorum(
    params: dict | str,
    request_created_at_ms: int,
    current_time_ms: int,
    current_approvals: int,
) -> str:
    """
    Time-Locked Quorum Decay (TLQD) calculation to resolve stalled multi-sig votes.
    """
    params_json = params if isinstance(params, str) else json.dumps(params)

    if _NATIVE_LOADED and _rust_core is not None:
        return _rust_core.calculate_decayed_quorum(params_json, request_created_at_ms, current_time_ms, current_approvals)

    p = json.loads(params_json)
    initial_req = p.get("initial_required_approvals", 3)
    min_floor = p.get("minimum_decay_floor_approvals", 2)
    interval_hours = p.get("decay_interval_hours", 48)
    enable_decay = p.get("enable_decay", True)

    if not enable_decay or interval_hours <= 0:
        needed = max(0, initial_req - current_approvals)
        approved = current_approvals >= initial_req
        return json.dumps({
            "is_approved": approved,
            "initial_approvals": initial_req,
            "current_required_approvals": initial_req,
            "current_approvals_count": current_approvals,
            "elapsed_hours": 0,
            "intervals_elapsed": 0,
            "approvals_still_needed": needed,
            "decay_applied": False,
            "status": "APPROVED_IMMEDIATE" if approved else "DECAY_DISABLED",
        })

    elapsed_ms = max(0, current_time_ms - request_created_at_ms)
    elapsed_hours = elapsed_ms // (1000 * 60 * 60)
    intervals = elapsed_hours // interval_hours
    max_intervals = p.get("max_decay_intervals")
    if max_intervals is not None:
        intervals = min(intervals, max_intervals)

    decayed_quorum = max(min_floor, initial_req - intervals) if intervals > 0 else initial_req
    needed = max(0, decayed_quorum - current_approvals)
    approved = current_approvals >= decayed_quorum

    status = "APPROVED_BY_DECAY" if (approved and decayed_quorum < initial_req) else ("APPROVED_IMMEDIATE" if approved else "PENDING_APPROVALS")

    return json.dumps({
        "is_approved": approved,
        "initial_approvals": initial_req,
        "current_required_approvals": decayed_quorum,
        "current_approvals_count": current_approvals,
        "elapsed_hours": elapsed_hours,
        "intervals_elapsed": intervals,
        "approvals_still_needed": needed,
        "decay_applied": decayed_quorum < initial_req,
        "status": status,
    })


def calculate_batch_health_grades(
    groups: list[dict] | str,
) -> str:
    """
    Evaluates financial health scores and letter grades (A+ to F) for groups.
    """
    groups_json = groups if isinstance(groups, str) else json.dumps(groups)

    if _NATIVE_LOADED and _rust_core is not None:
        return _rust_core.calculate_batch_health_grades(groups_json)

    items = json.loads(groups_json)
    results = []

    for item in items:
        completed = item.get("on_time_count", 0) + item.get("late_count", 0) + item.get("default_count", 0)
        if completed > 0:
            otp = (item.get("on_time_count", 0) / completed) * 100.0
            def_rate = (item.get("default_count", 0) / completed) * 100.0
        else:
            otp, def_rate = 100.0, 0.0

        active_members = item.get("total_active_members", 0)
        arrears_ratio = (item.get("members_in_arrears_count", 0) / active_members * 100.0) if active_members > 0 else 0.0

        on_time_pts = round(otp * 0.60)
        default_pts = round(max(0.0, 100.0 - def_rate) * 0.20)
        solvency_pts = round(max(0.0, 100.0 - arrears_ratio) * 0.20)
        composite = max(0, min(100, on_time_pts + default_pts + solvency_pts))

        if composite >= 95:
            grade, tier = "A+", "LOW"
        elif composite >= 85:
            grade, tier = "A", "LOW"
        elif composite >= 75:
            grade, tier = "B", "MODERATE"
        elif composite >= 60:
            grade, tier = "C", "MODERATE"
        elif composite >= 45:
            grade, tier = "D", "HIGH"
        else:
            grade, tier = "F", "CRITICAL"

        results.append({
            "group_id": item.get("group_id", ""),
            "on_time_repayment_rate_pct": round(otp, 1),
            "default_rate_pct": round(def_rate, 1),
            "arrears_member_ratio_pct": round(arrears_ratio, 1),
            "composite_score": composite,
            "grade": grade,
            "risk_tier": tier,
        })

    return json.dumps(results)


def validate_turn_swap_eligibility(
    requester: dict | str,
    target: dict | str,
    rules: dict | str,
) -> str:
    """
    Validates strict invariants for payout position swaps in rotating groups.
    """
    req_json = requester if isinstance(requester, str) else json.dumps(requester)
    target_json = target if isinstance(target, str) else json.dumps(target)
    rules_json = rules if isinstance(rules, str) else json.dumps(rules)

    if _NATIVE_LOADED and _rust_core is not None:
        return _rust_core.validate_turn_swap_eligibility(req_json, target_json, rules_json)

    r = json.loads(req_json)
    t = json.loads(target_json)
    rls = json.loads(rules_json)

    if rls.get("is_rotation_locked", False):
        return json.dumps({
            "is_permitted": False,
            "requester_new_cycle": r.get("assigned_cycle", 0),
            "target_new_cycle": t.get("assigned_cycle", 0),
            "rejection_reason": "Turn swapping is locked for this group by admin policy.",
        })

    if r.get("user_id") == t.get("user_id"):
        return json.dumps({
            "is_permitted": False,
            "requester_new_cycle": r.get("assigned_cycle", 0),
            "target_new_cycle": t.get("assigned_cycle", 0),
            "rejection_reason": "Cannot swap turn positions with yourself.",
        })

    if r.get("membership_status") != "ACTIVE" or t.get("membership_status") != "ACTIVE":
        return json.dumps({
            "is_permitted": False,
            "requester_new_cycle": r.get("assigned_cycle", 0),
            "target_new_cycle": t.get("assigned_cycle", 0),
            "rejection_reason": "Both members must be in ACTIVE status to execute a turn swap.",
        })

    if r.get("has_received_payout", False):
        return json.dumps({
            "is_permitted": False,
            "requester_new_cycle": r.get("assigned_cycle", 0),
            "target_new_cycle": t.get("assigned_cycle", 0),
            "rejection_reason": "Requester has already received a payout in this round.",
        })

    if t.get("has_received_payout", False):
        return json.dumps({
            "is_permitted": False,
            "requester_new_cycle": r.get("assigned_cycle", 0),
            "target_new_cycle": t.get("assigned_cycle", 0),
            "rejection_reason": "Target member has already received a payout in this round.",
        })

    if r.get("overdue_obligations_count", 0) > 0 or r.get("unpaid_penalties_count", 0) > 0:
        return json.dumps({
            "is_permitted": False,
            "requester_new_cycle": r.get("assigned_cycle", 0),
            "target_new_cycle": t.get("assigned_cycle", 0),
            "rejection_reason": "Requester has overdue obligations or unpaid late penalties.",
        })

    if t.get("overdue_obligations_count", 0) > 0 or t.get("unpaid_penalties_count", 0) > 0:
        return json.dumps({
            "is_permitted": False,
            "requester_new_cycle": r.get("assigned_cycle", 0),
            "target_new_cycle": t.get("assigned_cycle", 0),
            "rejection_reason": "Target member has overdue obligations or unpaid late penalties.",
        })

    earlier = min(r.get("assigned_cycle", 0), t.get("assigned_cycle", 0))
    current_cycle = rls.get("current_active_cycle", 1)
    if earlier <= current_cycle:
        return json.dumps({
            "is_permitted": False,
            "requester_new_cycle": r.get("assigned_cycle", 0),
            "target_new_cycle": t.get("assigned_cycle", 0),
            "rejection_reason": f"Cannot swap into or from cycle {earlier} because current round is already at or past cycle {current_cycle}.",
        })

    earlier_member = r if r.get("assigned_cycle", 0) < t.get("assigned_cycle", 0) else t
    if earlier_member.get("trust_score", 0) < rls.get("minimum_trust_score", 0):
        return json.dumps({
            "is_permitted": False,
            "requester_new_cycle": r.get("assigned_cycle", 0),
            "target_new_cycle": t.get("assigned_cycle", 0),
            "rejection_reason": f"Member moving to earlier cycle has trust score ({earlier_member.get('trust_score', 0)}) below group threshold ({rls.get('minimum_trust_score', 0)}).",
        })

    if earlier_member.get("kyc_tier", 0) < rls.get("minimum_kyc_tier", 1):
        return json.dumps({
            "is_permitted": False,
            "requester_new_cycle": r.get("assigned_cycle", 0),
            "target_new_cycle": t.get("assigned_cycle", 0),
            "rejection_reason": f"Member moving to earlier cycle has KYC tier ({earlier_member.get('kyc_tier', 0)}) below group threshold ({rls.get('minimum_kyc_tier', 1)}).",
        })

    return json.dumps({
        "is_permitted": True,
        "requester_new_cycle": t.get("assigned_cycle", 0),
        "target_new_cycle": r.get("assigned_cycle", 0),
        "rejection_reason": None,
    })


def calculate_base_deposit_fee(group_target_amount: int) -> str:
    """
    Computes tiered psychological fee breakdown for deposit amount.
    """
    if _NATIVE_LOADED and _rust_core is not None and hasattr(_rust_core, "calculate_base_deposit_fee"):
        return _rust_core.calculate_base_deposit_fee(group_target_amount)

    if group_target_amount <= 0:
        raise ValueError("group_target_amount must be a positive integer")

    if group_target_amount < 5_001:
        offset = 15
    elif group_target_amount < 10_001:
        offset = 16
    elif group_target_amount < 20_001:
        offset = 17
    elif group_target_amount < 50_001:
        offset = 18
    elif group_target_amount < 100_001:
        offset = 19
    elif group_target_amount < 500_001:
        offset = 21
    else:
        offset = 22

    mtn_fee = round(group_target_amount * 0.015)
    platform_fee = max(0, mtn_fee - offset)
    total_fee = mtn_fee + platform_fee
    charge_amount = group_target_amount + total_fee

    return json.dumps({
        "group_target_amount": group_target_amount,
        "mtn_fee": mtn_fee,
        "platform_fee": platform_fee,
        "total_fee": total_fee,
        "charge_amount": charge_amount,
        "psychological_offset": offset,
        "microbond_net_revenue": platform_fee,
    })


def calculate_target_deposit_fee(
    deposit_amount: int,
    current_saved_amount: int,
    target_goal_amount: int,
    assigned_milestone_threshold: float,
    fee_already_collected: bool = False,
    target_payout_fee: int = 979,
) -> str:
    """
    Computes MTN RequestToPay charge for Target Savings with milestone payout fee.
    """
    if _NATIVE_LOADED and _rust_core is not None and hasattr(_rust_core, "calculate_target_deposit_fee"):
        return _rust_core.calculate_target_deposit_fee(
            deposit_amount,
            current_saved_amount,
            target_goal_amount,
            assigned_milestone_threshold,
            fee_already_collected,
            target_payout_fee,
        )

    base = json.loads(calculate_base_deposit_fee(deposit_amount))
    new_cumulative = current_saved_amount + deposit_amount
    threshold_amount = round(target_goal_amount * assigned_milestone_threshold)

    should_charge = not fee_already_collected and (new_cumulative >= threshold_amount or new_cumulative >= target_goal_amount)
    payout_fee = target_payout_fee if should_charge else 0
    final_charge = base["charge_amount"] + payout_fee

    return json.dumps({
        "deposit_amount": deposit_amount,
        "base_charge_amount": base["charge_amount"],
        "mtn_deposit_fee": base["mtn_fee"],
        "microbond_deposit_fee": base["platform_fee"],
        "hidden_payout_fee": payout_fee,
        "final_charge_amount": final_charge,
        "is_fee_milestone": should_charge,
        "milestone_triggered_now": should_charge,
    })


def calculate_investment_deposit_fee(
    deposit_amount: int,
    current_annual_deposit_count: int,
    assigned_milestone_count: int,
    fee_collected_this_year: bool = False,
    target_payout_fee: int = 979,
) -> str:
    """
    Computes MTN RequestToPay charge for Investment Club share purchase with milestone payout fee.
    """
    if _NATIVE_LOADED and _rust_core is not None and hasattr(_rust_core, "calculate_investment_deposit_fee"):
        return _rust_core.calculate_investment_deposit_fee(
            deposit_amount,
            current_annual_deposit_count,
            assigned_milestone_count,
            fee_collected_this_year,
            target_payout_fee,
        )

    base = json.loads(calculate_base_deposit_fee(deposit_amount))
    this_deposit_number = current_annual_deposit_count + 1

    should_charge = not fee_collected_this_year and (this_deposit_number >= assigned_milestone_count)
    payout_fee = target_payout_fee if should_charge else 0
    final_charge = base["charge_amount"] + payout_fee

    return json.dumps({
        "deposit_amount": deposit_amount,
        "base_charge_amount": base["charge_amount"],
        "mtn_deposit_fee": base["mtn_fee"],
        "microbond_deposit_fee": base["platform_fee"],
        "hidden_payout_fee": payout_fee,
        "final_charge_amount": final_charge,
        "is_fee_milestone": should_charge,
        "this_deposit_number": this_deposit_number,
    })


def calculate_emergency_deposit_fee(
    deposit_amount: int,
    group_pending_payout_fees_count: int,
    target_payout_fee: int = 979,
) -> str:
    """
    Computes MTN RequestToPay charge for Welfare Fund clearing pending emergency payout fees.
    """
    if _NATIVE_LOADED and _rust_core is not None and hasattr(_rust_core, "calculate_emergency_deposit_fee"):
        return _rust_core.calculate_emergency_deposit_fee(
            deposit_amount,
            group_pending_payout_fees_count,
            target_payout_fee,
        )

    base = json.loads(calculate_base_deposit_fee(deposit_amount))
    fees_to_clear = group_pending_payout_fees_count
    total_payout_fee = fees_to_clear * target_payout_fee
    final_charge = base["charge_amount"] + total_payout_fee

    return json.dumps({
        "deposit_amount": deposit_amount,
        "base_charge_amount": base["charge_amount"],
        "mtn_deposit_fee": base["mtn_fee"],
        "microbond_deposit_fee": base["platform_fee"],
        "hidden_payout_fee": total_payout_fee,
        "final_charge_amount": final_charge,
        "cleared_pending_fee": fees_to_clear > 0,
        "fees_cleared": fees_to_clear,
    })


def validate_auction_bid(
    auction_status: str,
    current_time_ms: int,
    auction_end_time_ms: int,
    new_bid_amount: int,
    current_highest_bid_amount: int | None = None,
    anti_sniping_threshold_ms: int = 60000,
    clock_extension_ms: int = 60000,
) -> str:
    """
    Validates an incoming auction bid and evaluates anti-sniping popcorn timer extensions.
    """
    if _NATIVE_LOADED and _rust_core is not None and hasattr(_rust_core, "validate_auction_bid"):
        return _rust_core.validate_auction_bid(
            auction_status,
            current_time_ms,
            auction_end_time_ms,
            new_bid_amount,
            current_highest_bid_amount,
            anti_sniping_threshold_ms,
            clock_extension_ms,
        )

    if auction_status != "ACTIVE":
        return json.dumps({
            "is_valid": False,
            "rejection_reason": f"Auction is currently {auction_status}.",
            "clock_extended": False,
            "new_end_time": auction_end_time_ms,
        })

    if current_time_ms >= auction_end_time_ms:
        return json.dumps({
            "is_valid": False,
            "rejection_reason": "The bidding window has closed.",
            "clock_extended": False,
            "new_end_time": auction_end_time_ms,
        })

    if new_bid_amount <= 0:
        return json.dumps({
            "is_valid": False,
            "rejection_reason": "Bid amount must be positive.",
            "clock_extended": False,
            "new_end_time": auction_end_time_ms,
        })

    if current_highest_bid_amount is not None and new_bid_amount <= current_highest_bid_amount:
        return json.dumps({
            "is_valid": False,
            "rejection_reason": f"A bid of {current_highest_bid_amount} or higher already exists. Please submit a higher bid.",
            "clock_extended": False,
            "new_end_time": auction_end_time_ms,
        })

    time_remaining = auction_end_time_ms - current_time_ms
    if time_remaining < anti_sniping_threshold_ms:
        clock_extended = True
        new_end = current_time_ms + clock_extension_ms
    else:
        clock_extended = False
        new_end = auction_end_time_ms

    return json.dumps({
        "is_valid": True,
        "rejection_reason": None,
        "clock_extended": clock_extended,
        "new_end_time": new_end,
    })


def settle_auction_payout(
    gross_pool: int,
    winning_bid: int,
    member_count: int,
    reserve_fund_bps: int = 0,
) -> str:
    """
    Settles an auction payout, calculating net winner amount and distributing dividend surplus.
    """
    if _NATIVE_LOADED and _rust_core is not None and hasattr(_rust_core, "settle_auction_payout"):
        return _rust_core.settle_auction_payout(
            gross_pool,
            winning_bid,
            member_count,
            reserve_fund_bps,
        )

    if gross_pool <= 0:
        raise ValueError("gross_pool must be positive")
    if winning_bid < 0 or winning_bid > gross_pool:
        raise ValueError("winning_bid cannot be negative or exceed gross_pool")
    if member_count < 2:
        raise ValueError("member_count must be at least 2")

    reserve_holdback = (gross_pool * reserve_fund_bps) // 10_000
    net_winner_payout = gross_pool - reserve_holdback - winning_bid
    dividend_pool = winning_bid

    non_winning = member_count - 1
    dividend_per_member = dividend_pool // non_winning
    dividend_remainder = dividend_pool % non_winning

    reconciled = net_winner_payout + reserve_holdback + (dividend_per_member * non_winning) + dividend_remainder

    return json.dumps({
        "gross_pool": gross_pool,
        "reserve_holdback": reserve_holdback,
        "winning_bid_discount": winning_bid,
        "net_winner_payout": net_winner_payout,
        "dividend_pool": dividend_pool,
        "non_winning_members_count": non_winning,
        "dividend_per_member": dividend_per_member,
        "dividend_remainder": dividend_remainder,
        "invariant_verified": reconciled == gross_pool,
    })


def calculate_equal_split(total_bill: int, member_count: int) -> str:
    """
    Computes equal split with deterministic integer remainder distribution.
    """
    if _NATIVE_LOADED and _rust_core is not None and hasattr(_rust_core, "calculate_equal_split"):
        return _rust_core.calculate_equal_split(total_bill, member_count)

    if total_bill <= 0:
        raise ValueError("total_bill must be positive")
    if member_count == 0:
        raise ValueError("member_count cannot be zero")

    base_share = total_bill // member_count
    remainder = total_bill % member_count

    shares = [base_share + 1 if i < remainder else base_share for i in range(member_count)]

    return json.dumps({
        "total_bill": total_bill,
        "member_count": member_count,
        "base_share": base_share,
        "remainder_units": remainder,
        "member_shares": shares,
        "invariant_verified": sum(shares) == total_bill,
    })


def validate_custom_split(total_bill: int, shares: list[int]) -> str:
    """
    Validates whether custom split allocations exactly sum to total_bill.
    """
    if _NATIVE_LOADED and _rust_core is not None and hasattr(_rust_core, "validate_custom_split"):
        return _rust_core.validate_custom_split(total_bill, shares)

    if total_bill <= 0:
        return json.dumps({
            "is_valid": False,
            "total_bill": total_bill,
            "allocated_sum": 0,
            "discrepancy": -total_bill,
            "error_message": "total_bill must be positive",
        })

    for idx, s in enumerate(shares):
        if s < 0:
            return json.dumps({
                "is_valid": False,
                "total_bill": total_bill,
                "allocated_sum": sum(shares),
                "discrepancy": sum(shares) - total_bill,
                "error_message": f"Share at index {idx} cannot be negative ({s})",
            })

    allocated_sum = sum(shares)
    discrepancy = allocated_sum - total_bill
    is_valid = discrepancy == 0

    return json.dumps({
        "is_valid": is_valid,
        "total_bill": total_bill,
        "allocated_sum": allocated_sum,
        "discrepancy": discrepancy,
        "error_message": f"Total bill is {total_bill} UGX but allocated shares sum to {allocated_sum} UGX" if not is_valid else None,
    })


def is_name_similar(name_a: str, name_b: str, threshold: float = 75.0) -> str:
    """
    Token-sorted fuzzy string comparison helper.
    """
    if _NATIVE_LOADED and _rust_core is not None and hasattr(_rust_core, "is_name_similar"):
        return _rust_core.is_name_similar(name_a, name_b, threshold)

    if not name_a or not name_b or not name_a.strip() or not name_b.strip():
        return json.dumps({
            "is_similar": False,
            "similarity_percentage": 0.0,
            "normalized_a": "",
            "normalized_b": "",
        })

    clean_a = " ".join(sorted(name_a.lower().split()))
    clean_b = " ".join(sorted(name_b.lower().split()))

    if clean_a == clean_b:
        return json.dumps({
            "is_similar": True,
            "similarity_percentage": 100.0,
            "normalized_a": clean_a,
            "normalized_b": clean_b,
        })

    import difflib
    ratio = difflib.SequenceMatcher(None, clean_a, clean_b).ratio() * 100.0

    return json.dumps({
        "is_similar": ratio >= threshold,
        "similarity_percentage": round(ratio, 2),
        "normalized_a": clean_a,
        "normalized_b": clean_b,
    })


def calculate_single_health_grade(
    group_id: str,
    on_time_count: int,
    late_count: int,
    default_count: int,
    total_defaulted_amount_minor: int = 0,
    total_expected_amount_minor: int = 0,
    members_in_arrears_count: int = 0,
    total_active_members: int = 1,
) -> str:
    """
    Evaluates group financial health score and letter grade.
    Delegates to compiled Rust engine when available.
    """
    if _NATIVE_LOADED and _rust_core is not None and hasattr(_rust_core, "calculate_single_health_grade"):
        return _rust_core.calculate_single_health_grade(
            group_id,
            on_time_count,
            late_count,
            default_count,
            total_defaulted_amount_minor,
            total_expected_amount_minor,
            members_in_arrears_count,
            total_active_members,
        )

    completed = on_time_count + late_count + default_count
    if completed > 0:
        on_time_pct = (on_time_count / completed) * 100.0
        default_pct = (default_count / completed) * 100.0
    else:
        on_time_pct = 100.0
        default_pct = 0.0

    arrears_ratio_pct = (members_in_arrears_count / total_active_members * 100.0) if total_active_members > 0 else 0.0

    on_time_pts = round(on_time_pct * 0.60)
    default_pts = round(max(0.0, 100.0 - default_pct) * 0.20)
    solvency_pts = round(max(0.0, 100.0 - arrears_ratio_pct) * 0.20)

    composite_score = max(0, min(100, int(on_time_pts + default_pts + solvency_pts)))

    if composite_score >= 95:
        grade, risk_tier = "A+", "LOW"
    elif composite_score >= 85:
        grade, risk_tier = "A", "LOW"
    elif composite_score >= 75:
        grade, risk_tier = "B", "MODERATE"
    elif composite_score >= 60:
        grade, risk_tier = "C", "MODERATE"
    elif composite_score >= 45:
        grade, risk_tier = "D", "HIGH"
    else:
        grade, risk_tier = "F", "CRITICAL"

    return json.dumps({
        "group_id": group_id,
        "on_time_repayment_rate_pct": round(on_time_pct, 1),
        "default_rate_pct": round(default_pct, 1),
        "arrears_member_ratio_pct": round(arrears_ratio_pct, 1),
        "composite_score": composite_score,
        "grade": grade,
        "risk_tier": risk_tier,
    })


def evaluate_benefit_eligibility(
    require_guarantors: bool,
    required_guarantors_count: int,
    active_guarantors_count: int,
    trust_score: int,
    minimum_trust_score: Optional[int] = None,
) -> str:
    """
    Evaluates whether a member is eligible for a benefit or payout based on guarantor requirements.
    Delegates to compiled Rust engine when available.
    """
    if _NATIVE_LOADED and _rust_core is not None and hasattr(_rust_core, "evaluate_benefit_eligibility"):
        return _rust_core.evaluate_benefit_eligibility(
            require_guarantors,
            required_guarantors_count,
            active_guarantors_count,
            trust_score,
            minimum_trust_score,
        )

    if minimum_trust_score is not None and trust_score < minimum_trust_score:
        return json.dumps({
            "is_eligible": False,
            "active_guarantors_count": active_guarantors_count,
            "required_guarantors_count": required_guarantors_count,
            "trust_score": trust_score,
            "minimum_trust_score": minimum_trust_score,
            "status": "REJECTED_LOW_TRUST_SCORE",
            "rejection_reason": f"Member Trust Score ({trust_score}) is below the required minimum of {minimum_trust_score}."
        })

    if require_guarantors and active_guarantors_count < required_guarantors_count:
        return json.dumps({
            "is_eligible": False,
            "active_guarantors_count": active_guarantors_count,
            "required_guarantors_count": required_guarantors_count,
            "trust_score": trust_score,
            "minimum_trust_score": minimum_trust_score,
            "status": "REQUIRES_GUARANTOR",
            "rejection_reason": f"Benefit requires {required_guarantors_count} active guarantor(s), but only {active_guarantors_count} verified."
        })

    return json.dumps({
        "is_eligible": True,
        "active_guarantors_count": active_guarantors_count,
        "required_guarantors_count": required_guarantors_count,
        "trust_score": trust_score,
        "minimum_trust_score": minimum_trust_score,
        "status": "APPROVED",
        "rejection_reason": None
    })


def detect_guarantor_cycle(
    existing_edges: list,
    new_guarantor: str,
    new_borrower: str,
) -> bool:
    """
    Detects if adding a directed vouching edge (new_guarantor -> new_borrower)
    creates a cyclic dependency in the vouching graph.
    Delegates to compiled Rust engine when available.
    """
    if _NATIVE_LOADED and _rust_core is not None and hasattr(_rust_core, "detect_guarantor_cycle"):
        return _rust_core.detect_guarantor_cycle(existing_edges, new_guarantor, new_borrower)

    if new_guarantor == new_borrower:
        return True

    from collections import defaultdict, deque
    adj = defaultdict(list)
    for g, b in existing_edges:
        adj[str(g)].append(str(b))

    visited = set()
    queue = deque([str(new_borrower)])
    visited.add(str(new_borrower))

    while queue:
        curr = queue.popleft()
        if curr == str(new_guarantor):
            return True
        for neighbor in adj.get(curr, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return False


def evaluate_guarantor_capacity(
    guarantor_trust_score: int,
    total_contributed_minor: int,
    current_active_liability_minor: int,
    new_pledge_minor: int,
    bad_obligations_count: int = 0,
    min_guarantor_trust_score: int = 70,
    base_allowance_minor: int = 500_000,
) -> str:
    """
    Evaluates dynamic guarantor risk capacity based on trust score and contribution history.
    Delegates to compiled Rust engine when available.
    """
    if _NATIVE_LOADED and _rust_core is not None and hasattr(_rust_core, "evaluate_guarantor_capacity"):
        return _rust_core.evaluate_guarantor_capacity(
            guarantor_trust_score,
            total_contributed_minor,
            current_active_liability_minor,
            new_pledge_minor,
            bad_obligations_count,
            min_guarantor_trust_score,
            base_allowance_minor,
        )

    if bad_obligations_count > 0:
        return json.dumps({
            "is_approved": False,
            "dynamic_max_liability_minor": 0,
            "total_projected_liability_minor": current_active_liability_minor + new_pledge_minor,
            "remaining_capacity_minor": 0,
            "rejection_reason": "Guarantor currently has overdue or defaulted payments and cannot take on risk."
        })

    if guarantor_trust_score < min_guarantor_trust_score:
        return json.dumps({
            "is_approved": False,
            "dynamic_max_liability_minor": 0,
            "total_projected_liability_minor": current_active_liability_minor + new_pledge_minor,
            "remaining_capacity_minor": 0,
            "rejection_reason": f"Guarantor has a Trust Score of {guarantor_trust_score}. A minimum of {min_guarantor_trust_score} is required to vouch for others."
        })

    historical_weight = (total_contributed_minor * 5 * guarantor_trust_score) // 100
    dynamic_max_liability = max(base_allowance_minor, historical_weight)
    total_projected = current_active_liability_minor + new_pledge_minor

    if total_projected > dynamic_max_liability:
        remaining = max(0, dynamic_max_liability - current_active_liability_minor)
        return json.dumps({
            "is_approved": False,
            "dynamic_max_liability_minor": dynamic_max_liability,
            "total_projected_liability_minor": total_projected,
            "remaining_capacity_minor": remaining,
            "rejection_reason": f"Guarantor capacity exceeded. Remaining capacity is {remaining:,} UGX."
        })

    return json.dumps({
        "is_approved": True,
        "dynamic_max_liability_minor": dynamic_max_liability,
        "total_projected_liability_minor": total_projected,
        "remaining_capacity_minor": dynamic_max_liability - total_projected,
        "rejection_reason": None
    })


def evaluate_liquidity_reserve(
    total_balance_minor: int,
    buffer_percentage: float,
    requested_disbursal_minor: int,
) -> str:
    """
    Evaluates if a requested disbursal breaches the group's locked liquidity buffer percentage.
    Delegates to compiled Rust engine when available.
    """
    if _NATIVE_LOADED and _rust_core is not None and hasattr(_rust_core, "evaluate_liquidity_reserve"):
        return _rust_core.evaluate_liquidity_reserve(
            total_balance_minor,
            buffer_percentage,
            requested_disbursal_minor,
        )

    pct = max(0.0, min(100.0, float(buffer_percentage)))
    locked_buffer = int(round(max(0, total_balance_minor) * (pct / 100.0)))
    max_available = max(0, total_balance_minor - locked_buffer)

    if requested_disbursal_minor <= max_available:
        return json.dumps({
            "is_permitted": True,
            "total_balance_minor": total_balance_minor,
            "locked_buffer_minor": locked_buffer,
            "max_available_disbursal_minor": max_available,
            "requested_disbursal_minor": requested_disbursal_minor,
            "shortfall_minor": 0,
            "rejection_reason": None
        })
    else:
        shortfall = requested_disbursal_minor - max_available
        return json.dumps({
            "is_permitted": False,
            "total_balance_minor": total_balance_minor,
            "locked_buffer_minor": locked_buffer,
            "max_available_disbursal_minor": max_available,
            "requested_disbursal_minor": requested_disbursal_minor,
            "shortfall_minor": shortfall,
            "rejection_reason": f"Requested disbursal of {requested_disbursal_minor:,} UGX breaches the {int(pct)}% liquidity buffer. Maximum permitted disbursal is {max_available:,} UGX."
        })


def calculate_escalated_late_fee(
    base_fee_minor: int,
    late_days: int,
    grace_period_days: int = 0,
    escalation_enabled: bool = True,
) -> str:
    """
    Calculates escalated late penalty fees across missed cycle windows.
    Delegates to compiled Rust engine when available.
    """
    if _NATIVE_LOADED and _rust_core is not None and hasattr(_rust_core, "calculate_escalated_late_fee"):
        return _rust_core.calculate_escalated_late_fee(
            base_fee_minor,
            late_days,
            grace_period_days,
            escalation_enabled,
        )

    if late_days <= grace_period_days:
        return json.dumps({
            "base_fee_minor": base_fee_minor,
            "total_late_fee_minor": 0,
            "late_days": max(0, late_days),
            "escalation_multiplier": 1.0,
            "is_escalated": False
        })

    overdue_days = late_days - grace_period_days
    if not escalation_enabled:
        return json.dumps({
            "base_fee_minor": base_fee_minor,
            "total_late_fee_minor": base_fee_minor,
            "late_days": late_days,
            "escalation_multiplier": 1.0,
            "is_escalated": False
        })

    if overdue_days <= 7:
        multiplier = 1.0
    elif overdue_days <= 14:
        multiplier = 1.5
    else:
        multiplier = 2.0

    total_fee = int(round(base_fee_minor * multiplier))
    return json.dumps({
        "base_fee_minor": base_fee_minor,
        "total_late_fee_minor": total_fee,
        "late_days": late_days,
        "escalation_multiplier": multiplier,
        "is_escalated": multiplier > 1.0
    })






