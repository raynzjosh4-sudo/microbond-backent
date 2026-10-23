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

        # Case 1: D vouches for A -> acyclic
        assert detect_guarantor_cycle(existing, "user_D", "user_A") is False

        # Case 2: C attempts to vouch for A -> creates cycle C -> A -> B -> C!
        assert detect_guarantor_cycle(existing, "user_C", "user_A") is True

        # Case 3: Self-guarantee
        assert detect_guarantor_cycle(existing, "user_X", "user_X") is True

    def test_evaluate_cross_group_exposure(self):
        from app.core.microbond_core import evaluate_cross_group_exposure

        # Case 1: Clean eligible user
        res_good = json.loads(evaluate_cross_group_exposure(
            user_active_rotating_groups=2,
            max_allowed_rotating=10,
            has_unpaid_hit_and_run=False,
            late_obligations_count=0,
            historical_penalties=0,
            max_historical_penalties=3,
            user_trust_score=80,
            min_trust_score=70,
            user_kyc_tier=2,
            min_kyc_tier=1,
            is_payout_order_locked=False,
        ))
        assert res_good["is_eligible"] is True
        assert res_good["risk_tier"] == "APPROVED"

        # Case 2: Hit-and-run defaulter
        res_hnr = json.loads(evaluate_cross_group_exposure(
            user_active_rotating_groups=2,
            has_unpaid_hit_and_run=True,
        ))
        assert res_hnr["is_eligible"] is False
        assert res_hnr["risk_tier"] == "REJECTED_HIT_AND_RUN"

        # Case 3: Over capacity
        res_cap = json.loads(evaluate_cross_group_exposure(
            user_active_rotating_groups=10,
            max_allowed_rotating=10,
        ))
        assert res_cap["is_eligible"] is False
        assert res_cap["risk_tier"] == "REJECTED_OVER_CAPACITY"

        # Case 4: Active arrears
        res_arr = json.loads(evaluate_cross_group_exposure(
            user_active_rotating_groups=1,
            late_obligations_count=2,
        ))
        assert res_arr["is_eligible"] is False
        assert res_arr["risk_tier"] == "REJECTED_ARREARS"

    def test_evaluate_guarantor_capacity(self):
        from app.core.microbond_core import evaluate_guarantor_capacity

        # Case 1: Approved capacity
        res_ok = json.loads(evaluate_guarantor_capacity(
            guarantor_trust_score=80,
            total_contributed_minor=100_000,
            current_active_liability_minor=200_000,
            new_pledge_minor=250_000,
            bad_obligations_count=0,
            min_guarantor_trust_score=70,
            base_allowance_minor=500_000,
        ))
        assert res_ok["is_approved"] is True
        assert res_ok["dynamic_max_liability_minor"] == 500_000
        assert res_ok["remaining_capacity_minor"] == 50_000

        # Case 2: Over-leveraged
        res_over = json.loads(evaluate_guarantor_capacity(
            guarantor_trust_score=80,
            total_contributed_minor=100_000,
            current_active_liability_minor=300_000,
            new_pledge_minor=250_000,
            base_allowance_minor=500_000,
        ))
        assert res_over["is_approved"] is False

    def test_evaluate_escrow_release(self):
        from app.core.microbond_core import evaluate_escrow_release

        # Case 1: Active dispute blocks release
        res_disp = json.loads(evaluate_escrow_release(
            timelock_expired=True,
            milestones_total=3,
            milestones_completed=3,
            signers_required=2,
            signatures_collected=2,
            dispute_active=True,
            rule_mode="ALL_CONDITIONS",
        ))
        assert res_disp["release_permitted"] is False
        assert res_disp["status"] == "DISPUTED"

        # Case 2: All conditions met
        res_all = json.loads(evaluate_escrow_release(
            timelock_expired=True,
            milestones_total=3,
            milestones_completed=3,
            signers_required=2,
            signatures_collected=2,
            dispute_active=False,
            rule_mode="ALL_CONDITIONS",
        ))
        assert res_all["release_permitted"] is True
        assert res_all["status"] == "PERMITTED"

        # Case 3: Timelock or consensus mode
        res_or = json.loads(evaluate_escrow_release(
            timelock_expired=False,
            signers_required=3,
            signatures_collected=3,
            dispute_active=False,
            rule_mode="TIMELOCK_OR_CONSENSUS",
        ))
        assert res_or["release_permitted"] is True
        assert res_or["status"] == "PERMITTED"

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


class TestOption2WiredServices:
    def test_standard_fixed_matrix_generator_service(self):
        from unittest.mock import MagicMock
        from datetime import datetime, timezone
        from app.services.group.matrix_generators.standard_fixed import generate_standard_fixed_matrix
        from app.models.group.finance import MemberObligation, GroupPayout

        class MockMember:
            def __init__(self, uid):
                self.user_id = uid

        class MockSettings:
            reserve_fund_percentage = 0.05

        class MockDetails:
            payouts_per_cycle = 1
            collection_frequency_days = 7
            contribution_amount = 50000

        members = [MockMember(f"user_{i}") for i in range(1, 11)]
        session = MagicMock()

        num_cycles = generate_standard_fixed_matrix(
            session=session,
            group_id="grp_fixed_100",
            members=members,
            settings=MockSettings(),
            details=MockDetails(),
            start_date=datetime.now(timezone.utc),
        )

        assert num_cycles == 10
        assert session.bulk_insert_mappings.call_count == 2

        # First call is MemberObligation
        call_0 = session.bulk_insert_mappings.call_args_list[0]
        assert call_0[0][0] == MemberObligation
        obligations = call_0[0][1]
        assert len(obligations) == 100
        assert obligations[0]["group_id"] == "grp_fixed_100"
        assert obligations[0]["amount_due"] == 50000
        assert obligations[0]["amount_paid"] == 0
        assert obligations[0]["status"] == "PENDING"

        # Second call is GroupPayout
        call_1 = session.bulk_insert_mappings.call_args_list[1]
        assert call_1[0][0] == GroupPayout
        payouts = call_1[0][1]
        assert len(payouts) == 10
        assert payouts[0]["group_id"] == "grp_fixed_100"
        assert payouts[0]["amount_expected"] == 475000
        assert payouts[0]["amount_received"] == 0
        assert payouts[0]["user_id"] == "user_1"

    def test_auction_bidding_matrix_generator_service(self):
        from unittest.mock import MagicMock
        from datetime import datetime, timezone
        from app.services.group.matrix_generators.auction_bidding import generate_auction_bidding_matrix
        from app.models.group.finance import MemberObligation, GroupPayout

        class MockMember:
            def __init__(self, uid):
                self.user_id = uid

        class MockSettings:
            reserve_fund_percentage = 0.05

        class MockDetails:
            payouts_per_cycle = 1
            collection_frequency_days = 7
            contribution_amount = 50000

        members = [MockMember(f"user_{i}") for i in range(1, 11)]
        session = MagicMock()

        num_cycles = generate_auction_bidding_matrix(
            session=session,
            group_id="grp_bid_200",
            members=members,
            settings=MockSettings(),
            details=MockDetails(),
            start_date=datetime.now(timezone.utc),
        )

        assert num_cycles == 10
        assert session.bulk_insert_mappings.call_count == 2

        call_1 = session.bulk_insert_mappings.call_args_list[1]
        assert call_1[0][0] == GroupPayout
        payouts = call_1[0][1]
        assert len(payouts) == 10
        # In auction bidding, user_id is None pending auction
        assert payouts[0]["user_id"] is None
        assert payouts[0]["amount_expected"] == 475000

    def test_surplus_allocation_service(self):
        from app.services.fee_engines.rotating.surplus import allocate_surplus_to_future_cycles
        from app.services.fee_engines.rotating.surplus.schemas.coverage_status import CoverageStatus

        # 1. Full coverage test
        res_full = allocate_surplus_to_future_cycles(
            surplus_amount_ugx=100000,
            current_cycle_number=1,
            standard_contribution_amount=50000,
            max_cycles_in_group=10,
        )
        assert res_full.total_surplus_ugx == 100000
        assert res_full.cycles_fully_covered_count == 2
        assert res_full.fully_covered_cycles == [2, 3]
        assert res_full.partially_covered_cycle is None
        assert res_full.unallocated_residual_ugx == 0
        assert res_full.next_cycle_requiring_payment == 4
        assert len(res_full.coverage_breakdown) == 2
        assert res_full.coverage_breakdown[0].status == CoverageStatus.FULLY_COVERED

        # 2. Partial coverage test
        res_partial = allocate_surplus_to_future_cycles(
            surplus_amount_ugx=70000,
            current_cycle_number=1,
            standard_contribution_amount=50000,
            max_cycles_in_group=10,
        )
        assert res_partial.cycles_fully_covered_count == 1
        assert res_partial.fully_covered_cycles == [2]
        assert res_partial.partially_covered_cycle is not None
        assert res_partial.partially_covered_cycle.cycle_number == 3
        assert res_partial.partially_covered_cycle.amount_allocated == 20000
        assert res_partial.partially_covered_cycle.shortfall == 30000
        assert res_partial.partially_covered_cycle.status == CoverageStatus.PARTIALLY_COVERED

        # 3. Zero surplus test
        res_zero = allocate_surplus_to_future_cycles(
            surplus_amount_ugx=0,
            current_cycle_number=2,
            standard_contribution_amount=50000,
        )
        assert res_zero.total_surplus_ugx == 0
        assert res_zero.cycles_fully_covered_count == 0
        assert res_zero.next_cycle_requiring_payment == 3

    def test_flexible_rotate_deposit_service(self):
        from app.services.fee_engines.rotating.amortizer import calculate_flexible_rotate_deposit
        from app.services.fee_engines.rotating.amortizer.schemas.member_deposit_schedule import TARGET_PAYOUT_FEE

        # 1. Milestone triggered
        res_trig = calculate_flexible_rotate_deposit(
            deposit_amount=25000,
            current_saved_amount=30000,
            assigned_value_milestone=50000,
            fee_already_collected=False,
        )
        assert res_trig.milestone_triggered_now is True
        assert res_trig.hidden_payout_fee == TARGET_PAYOUT_FEE
        assert res_trig.new_cumulative_total == 55000
        assert res_trig.final_charge_amount == res_trig.base_charge_amount + TARGET_PAYOUT_FEE

        # 2. Milestone not yet reached
        res_no = calculate_flexible_rotate_deposit(
            deposit_amount=10000,
            current_saved_amount=10000,
            assigned_value_milestone=50000,
            fee_already_collected=False,
        )
        assert res_no.milestone_triggered_now is False
        assert res_no.hidden_payout_fee == 0
        assert res_no.new_cumulative_total == 20000
        assert res_no.final_charge_amount == res_no.base_charge_amount

        # 3. Milestone reached but fee already collected
        res_already = calculate_flexible_rotate_deposit(
            deposit_amount=25000,
            current_saved_amount=55000,
            assigned_value_milestone=50000,
            fee_already_collected=True,
        )
        assert res_already.milestone_triggered_now is False
        assert res_already.hidden_payout_fee == 0




