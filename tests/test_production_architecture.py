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

