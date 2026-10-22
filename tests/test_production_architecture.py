import json
import uuid
import pytest
from app.core.microbond_core import (
    check_join_rules,
    calculate_rotating_payout,
    calculate_penalty,
    canonical_audit_hash,
    is_native_loaded,
)
from app.models.infrastructure.idempotency import CommandIdempotency
from app.models.infrastructure.audit_event import AuditEvent


class TestMicrobondCoreDomainEngine:
    def test_native_or_reference_engine_loads(self):
        # Engine must always be active (either native Rust binary or reference engine)
        assert check_join_rules is not None
        assert calculate_rotating_payout is not None
        assert canonical_audit_hash is not None

    def test_check_join_rules_capacity_rejection(self):
        res = json.loads(check_join_rules(
            member_count=10,
            max_members=10,
            already_member_or_pending=False,
            has_arrears=False,
            trust_score=80,
            minimum_trust_score=50,
            kyc_tier=2,
            required_kyc_tier=1,
        ))
        assert res["status"] == "REJECTED"
        assert res["reason_code"] == "GROUP_FULL"

    def test_check_join_rules_arrears_rejection(self):
        res = json.loads(check_join_rules(
            member_count=5,
            max_members=10,
            already_member_or_pending=False,
            has_arrears=True,
            trust_score=80,
            minimum_trust_score=50,
            kyc_tier=2,
            required_kyc_tier=1,
        ))
        assert res["status"] == "REJECTED"
        assert res["reason_code"] == "ARREARS"

    def test_check_join_rules_kyc_rejection(self):
        res = json.loads(check_join_rules(
            member_count=5,
            max_members=10,
            already_member_or_pending=False,
            has_arrears=False,
            trust_score=80,
            minimum_trust_score=50,
            kyc_tier=1,
            required_kyc_tier=2,
        ))
        assert res["status"] == "REJECTED"
        assert res["reason_code"] == "KYC_TIER"

    def test_check_join_rules_trust_score_rejection(self):
        res = json.loads(check_join_rules(
            member_count=5,
            max_members=10,
            already_member_or_pending=False,
            has_arrears=False,
            trust_score=40,
            minimum_trust_score=50,
            kyc_tier=2,
            required_kyc_tier=1,
        ))
        assert res["status"] == "REJECTED"
        assert res["reason_code"] == "TRUST_SCORE"

    def test_check_join_rules_guarantor_required(self):
        res = json.loads(check_join_rules(
            member_count=5,
            max_members=10,
            already_member_or_pending=False,
            has_arrears=False,
            trust_score=80,
            minimum_trust_score=50,
            kyc_tier=2,
            required_kyc_tier=1,
            requires_guarantor=True,
        ))
        assert res["status"] == "PENDING_GUARANTOR"

    def test_check_join_rules_admin_approval_required(self):
        res = json.loads(check_join_rules(
            member_count=5,
            max_members=10,
            already_member_or_pending=False,
            has_arrears=False,
            trust_score=80,
            minimum_trust_score=50,
            kyc_tier=2,
            required_kyc_tier=1,
            requires_admin_approval=True,
        ))
        assert res["status"] == "PENDING_APPROVAL"

    def test_check_join_rules_active_direct_join(self):
        res = json.loads(check_join_rules(
            member_count=5,
            max_members=10,
            already_member_or_pending=False,
            has_arrears=False,
            trust_score=80,
            minimum_trust_score=50,
            kyc_tier=2,
            required_kyc_tier=1,
        ))
        assert res["status"] == "ACTIVE"

    def test_calculate_rotating_payout_success(self):
        # 50,000 UGX x 10 members = 500,000 UGX
        res = json.loads(calculate_rotating_payout(
            contribution_minor=50_000,
            member_count=10,
            late_days=0,
            grace_period_days=3,
            late_fee_minor=5_000,
        ))
        assert res["payout_minor"] == 500_000
        assert res["penalty_minor"] == 0
        assert res["net_payout_minor"] == 500_000
        assert res["currency"] == "UGX"

    def test_calculate_rotating_payout_with_penalty(self):
        res = json.loads(calculate_rotating_payout(
            contribution_minor=50_000,
            member_count=10,
            late_days=5,
            grace_period_days=3,
            late_fee_minor=5_000,
        ))
        assert res["payout_minor"] == 500_000
        assert res["penalty_minor"] == 5_000
        assert res["net_payout_minor"] == 495_000

    def test_calculate_rotating_payout_invalid_inputs(self):
        with pytest.raises(ValueError):
            calculate_rotating_payout(contribution_minor=0, member_count=10)
        with pytest.raises(ValueError):
            calculate_rotating_payout(contribution_minor=50_000, member_count=0)

    def test_calculate_penalty(self):
        # Within grace period -> 0 penalty
        within_grace = json.loads(calculate_penalty(
            amount_minor=100_000,
            late_days=2,
            grace_period_days=3,
            penalty_fixed_minor=2_000,
            penalty_daily_rate_bps=50,
        ))
        assert within_grace["penalty_minor"] == 0
        assert not within_grace["is_late"]

        # Past grace period (5 days late, grace is 3 days -> 2 days overdue)
        # Fixed: 2,000. Daily rate: 100,000 * 50 / 10,000 = 500. Variable: 500 * 2 = 1,000.
        # Total: 3,000.
        past_grace = json.loads(calculate_penalty(
            amount_minor=100_000,
            late_days=5,
            grace_period_days=3,
            penalty_fixed_minor=2_000,
            penalty_daily_rate_bps=50,
        ))
        assert past_grace["penalty_minor"] == 3_000
        assert past_grace["is_late"]

    def test_canonical_audit_hash(self):
        genesis_hash = "0" * 64
        payload = '{"action":"JOIN_REQUESTED","user_id":"test-user"}'
        h1 = canonical_audit_hash(genesis_hash, payload)
        h2 = canonical_audit_hash(genesis_hash, payload)
        assert h1 == h2
        assert len(h1) == 64

        # Chaining
        h3 = canonical_audit_hash(h1, '{"action":"MEMBER_ACTIVATED"}')
        assert h3 != h1
        assert len(h3) == 64

    def test_idempotency_and_audit_service_transaction(self):
        from sqlmodel import SQLModel, create_engine, Session
        import app.models.user.user  # Ensures 'user' table is in metadata
        from app.services.audit_service import AuditService
        from app.core.db_idempotency import check_db_idempotency, record_db_idempotency

        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        user_id = uuid.uuid4()
        req_id = "req_test_123"

        with Session(engine) as session:
            # First check -> should be None
            cached = check_db_idempotency(session, user_id, req_id)
            assert cached is None

            # Record idempotency
            payload = {"status": "success", "membership_status": "ACTIVE"}
            record_db_idempotency(session, user_id, req_id, payload)

            # Record audit event
            event = AuditService.record_event(
                session=session,
                action="JOIN_REQUESTED",
                entity_type="GROUP",
                entity_id="grp_abc",
                payload=payload,
                actor_user_id=user_id,
            )
            assert event.current_hash is not None
            assert len(event.current_hash) == 64
            session.commit()

        with Session(engine) as session:
            # Second check -> should return cached payload
            cached = check_db_idempotency(session, user_id, req_id)
            assert cached is not None
            assert cached["membership_status"] == "ACTIVE"

    def test_generate_cycle_matrix(self):
        from app.core.microbond_core import generate_cycle_matrix
        members = [f"user_{i}" for i in range(1, 11)]
        res = json.loads(generate_cycle_matrix(
            member_user_ids=members,
            group_type="STANDARD",
            contribution_minor=50_000,
            payouts_per_cycle=1,
            reserve_fund_bps=500, # 5%
            collection_frequency_days=7,
            start_epoch_seconds=1_700_000_000,
            created_at_epoch_seconds=1_700_000_000,
        ))
        assert res["num_cycles"] == 10
        assert res["member_count"] == 10
        assert res["gross_pool_minor"] == 500_000
        assert res["reserve_held_minor"] == 25_000 # 5% of 500k
        assert res["net_payout_minor"] == 475_000
        assert len(res["obligations"]) == 100
        assert len(res["payouts"]) == 10
        assert res["payouts"][0]["user_id"] == "user_1"
        assert res["payouts"][9]["user_id"] == "user_10"

    def test_allocate_surplus_waterfall(self):
        from app.core.microbond_core import allocate_surplus_waterfall
        # 100,000 covers 2 full cycles (cycle 2 and 3)
        res = json.loads(allocate_surplus_waterfall(
            surplus_amount=100_000,
            current_cycle_number=1,
            standard_contribution=50_000,
            max_cycles=10,
        ))
        assert res["cycles_fully_covered_count"] == 2
        assert res["fully_covered_cycles"] == [2, 3]
        assert res["partially_covered_cycle"] is None
        assert res["unallocated_residual"] == 0

        # 70,000 covers cycle 2 fully and cycle 3 partially (20k allocated, 30k shortfall)
        partial_res = json.loads(allocate_surplus_waterfall(
            surplus_amount=70_000,
            current_cycle_number=1,
            standard_contribution=50_000,
            max_cycles=10,
        ))
        assert partial_res["cycles_fully_covered_count"] == 1
        assert partial_res["fully_covered_cycles"] == [2]
        assert partial_res["partially_covered_cycle"] == 3
        assert partial_res["coverage_details"][1]["amount_allocated"] == 20_000
        assert partial_res["coverage_details"][1]["shortfall"] == 30_000

    def test_calculate_flexible_rotate_deposit(self):
        from app.core.microbond_core import calculate_flexible_rotate_deposit
        res = json.loads(calculate_flexible_rotate_deposit(
            deposit_amount=25_000,
            current_saved_amount=30_000,
            assigned_value_milestone=50_000,
            fee_already_collected=False,
            target_payout_fee=1500,
            mtn_flat_fee=500,
            platform_fee_bps=100, # 1% = 250
        ))
        assert res["milestone_triggered_now"] is True
        assert res["microbond_base_fee"] == 250
        assert res["hidden_payout_fee"] == 1500
        assert res["final_charge_amount"] == 25_000 + 500 + 250 + 1500
        assert res["new_cumulative_total"] == 55_000

    def test_detect_guarantor_cycle(self):
        from app.core.microbond_core import detect_guarantor_cycle
        # Graph: A -> B, B -> C
        existing = [("user_A", "user_B"), ("user_B", "user_C")]

        # Case 1: C vouches for D -> valid acyclic extension
        res_acyclic = json.loads(detect_guarantor_cycle(existing, new_borrower="user_D", new_guarantor="user_C"))
        assert res_acyclic["has_cycle"] is False
        assert len(res_acyclic["cycle_path"]) == 0

        # Case 2: C attempts to vouch for A -> creates cycle C -> A -> B -> C!
        res_cyclic = json.loads(detect_guarantor_cycle(existing, new_borrower="user_A", new_guarantor="user_C"))
        assert res_cyclic["has_cycle"] is True
        assert "user_C" in res_cyclic["cycle_path"]
        assert "user_A" in res_cyclic["cycle_path"]
        assert "Circular guarantor collusion detected" in res_cyclic["explanation"]

        # Case 3: Self-guarantee
        res_self = json.loads(detect_guarantor_cycle(existing, new_borrower="user_A", new_guarantor="user_A"))
        assert res_self["has_cycle"] is True
        assert "Self-guarantee" in res_self["explanation"]

    def test_evaluate_cross_group_exposure(self):
        from app.core.microbond_core import evaluate_cross_group_exposure
        rules = {
            "group_type": "MERRY_GO_ROUND",
            "max_active_rotating_groups": 10,
            "minimum_trust_score": 60,
            "minimum_kyc_tier": 2,
            "max_historical_penalties": 3,
            "payout_order_locked": False,
            "base_guarantor_allowance_minor": 500_000_00,
            "guarantor_leverage_multiplier": 5,
        }

        # Case 1: Clean eligible user
        good_user = {
            "user_id": "usr_good",
            "trust_score": 85,
            "kyc_tier": 2,
            "active_rotating_groups": 2,
            "has_unpaid_hit_and_run_payout": False,
            "late_or_defaulted_obligations_count": 0,
            "historical_penalties_count": 0,
            "total_active_guarantor_liability_minor": 100_000_00,
            "total_historical_contributed_minor": 200_000_00,
        }
        res_good = json.loads(evaluate_cross_group_exposure(good_user, rules))
        assert res_good["is_eligible"] is True
        assert res_good["risk_score"] >= 80
        assert res_good["dynamic_guarantor_capacity_minor"] >= 500_000_00

        # Case 2: Hit-and-run defaulter
        hnr_user = dict(good_user, has_unpaid_hit_and_run_payout=True)
        res_hnr = json.loads(evaluate_cross_group_exposure(hnr_user, rules))
        assert res_hnr["is_eligible"] is False
        assert res_hnr["rejection_code"] == "HIT_AND_RUN_DEBT"

        # Case 3: User with active arrears
        arrears_user = dict(good_user, late_or_defaulted_obligations_count=2)
        res_arr = json.loads(evaluate_cross_group_exposure(arrears_user, rules))
        assert res_arr["is_eligible"] is False
        assert res_arr["rejection_code"] == "ACTIVE_ARREARS"

        # Case 4: Group cap exceeded
        capped_user = dict(good_user, active_rotating_groups=10)
        res_cap = json.loads(evaluate_cross_group_exposure(capped_user, rules))
        assert res_cap["is_eligible"] is False
        assert res_cap["rejection_code"] == "MAX_GROUPS_EXCEEDED"

    def test_evaluate_escrow_release(self):
        from app.core.microbond_core import evaluate_escrow_release
        reqs = {
            "timelock_until_epoch_seconds": 1_700_000_000,
            "required_approvals_count": 3,
            "required_milestones_count": 2,
            "minimum_reserve_balance_minor": 50_000_00,
            "require_unanimous_if_disputed": False,
        }

        # Case 1: Satisfied release
        facts_ok = {
            "current_epoch_seconds": 1_700_000_100, # Passed timelock
            "approved_signatures_count": 3, # Quorum reached
            "completed_milestones_count": 2, # Milestones met
            "is_dispute_active": False, # Dispute free
            "current_pool_balance_minor": 200_000_00,
            "proposed_release_amount_minor": 100_000_00, # Leaves 100k >= 50k reserve
        }
        res_ok = json.loads(evaluate_escrow_release(reqs, facts_ok))
        assert res_ok["release_permitted"] is True
        assert res_ok["disposition"] == "RELEASE_PERMITTED"
        assert len(res_ok["blocking_reasons"]) == 0

        # Case 2: Blocked by active dispute and insufficient signers
        facts_blocked = dict(facts_ok, is_dispute_active=True, approved_signatures_count=2)
        res_blocked = json.loads(evaluate_escrow_release(reqs, facts_blocked))
        assert res_blocked["release_permitted"] is False
        assert res_blocked["disposition"] == "RELEASE_BLOCKED"
        assert len(res_blocked["blocking_reasons"]) >= 2

    def test_calculate_decayed_quorum(self):
        from app.core.microbond_core import calculate_decayed_quorum
        params = {
            "initial_required_approvals": 5,
            "minimum_decay_floor_approvals": 3,
            "decay_interval_hours": 24,
            "max_decay_intervals": 3,
            "enable_decay": True,
        }
        created_at_ms = 1_000_000_000_000

        # At t = 0 hours, approvals = 3 -> not enough yet (needs 5)
        res_t0 = json.loads(calculate_decayed_quorum(params, created_at_ms, created_at_ms, current_approvals=3))
        assert res_t0["is_approved"] is False
        assert res_t0["current_required_approvals"] == 5

        # After 48 hours (2 intervals), required decays from 5 down to 3
        now_48h = created_at_ms + (48 * 3600 * 1000)
        res_48h = json.loads(calculate_decayed_quorum(params, created_at_ms, now_48h, current_approvals=3))
        assert res_48h["is_approved"] is True
        assert res_48h["current_required_approvals"] == 3
        assert res_48h["status"] == "APPROVED_BY_DECAY"

    def test_calculate_batch_health_grades(self):
        from app.core.microbond_core import calculate_batch_health_grades
        batch = [
            {
                "group_id": "grp_stellar",
                "on_time_count": 98,
                "late_count": 2,
                "default_count": 0,
                "total_defaulted_amount_minor": 0,
                "total_expected_amount_minor": 10_000_000,
                "members_in_arrears_count": 0,
                "total_active_members": 20,
            },
            {
                "group_id": "grp_troubled",
                "on_time_count": 20,
                "late_count": 30,
                "default_count": 50,
                "total_defaulted_amount_minor": 5_000_000,
                "total_expected_amount_minor": 10_000_000,
                "members_in_arrears_count": 12,
                "total_active_members": 20,
            }
        ]
        res = json.loads(calculate_batch_health_grades(batch))
        assert len(res) == 2
        assert res[0]["grade"] in ("A+", "A")
        assert res[0]["risk_tier"] == "LOW"
        assert res[1]["grade"] in ("D", "F")
        assert res[1]["risk_tier"] in ("HIGH", "CRITICAL")

    def test_validate_turn_swap_invariants(self):
        from app.core.microbond_core import validate_turn_swap_eligibility
        rules = {
            "current_active_cycle": 2,
            "minimum_trust_score": 70,
            "minimum_kyc_tier": 2,
            "is_rotation_locked": False,
        }
        member_a = {
            "user_id": "usr_a",
            "assigned_cycle": 3,
            "membership_status": "ACTIVE",
            "has_received_payout": False,
            "overdue_obligations_count": 0,
            "unpaid_penalties_count": 0,
            "trust_score": 80,
            "kyc_tier": 2,
        }
        member_b = {
            "user_id": "usr_b",
            "assigned_cycle": 7,
            "membership_status": "ACTIVE",
            "has_received_payout": False,
            "overdue_obligations_count": 0,
            "unpaid_penalties_count": 0,
            "trust_score": 85,
            "kyc_tier": 2,
        }

        # Case 1: Valid swap between Cycle 3 and Cycle 7
        res_ok = json.loads(validate_turn_swap_eligibility(member_a, member_b, rules))
        assert res_ok["is_permitted"] is True
        assert res_ok["requester_new_cycle"] == 7
        assert res_ok["target_new_cycle"] == 3

        # Case 2: Rejected if member has received payout
        member_paid = dict(member_a, has_received_payout=True)
        res_paid = json.loads(validate_turn_swap_eligibility(member_paid, member_b, rules))
        assert res_paid["is_permitted"] is False
        assert "already received a payout" in res_paid["rejection_reason"]

        # Case 3: Rejected if earlier cycle is already in the past
        past_rules = dict(rules, current_active_cycle=4) # Cycle 3 already passed
        res_past = json.loads(validate_turn_swap_eligibility(member_a, member_b, past_rules))
        assert res_past["is_permitted"] is False
        assert "past cycle" in res_past["rejection_reason"]



