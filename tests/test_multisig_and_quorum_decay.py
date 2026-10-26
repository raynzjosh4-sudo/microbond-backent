import pytest
import uuid
import time
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.rotating.rotating_group_details import RotatingGroupDetails
from app.models.group.settings.group_governance_settings import GroupGovernanceSettings
from app.models.group.wallet.group_wallet import GroupWallet
from app.models.group.finance import GroupPayout, PayoutSignature
from app.models.group.chat import GroupChatMessage
from app.cronjobs.finance.quorum_decay_processor import process_time_locked_quorum_decay
from app.cronjobs.finance.payout_disbursement_worker.process_single_payout import process_single_payout
from app.services.mobile_money.disbursement_service import DisbursementService, DisbursementResult
from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.utils.time.now_epoch_ms import now_epoch_ms


@pytest.fixture(name="db_session")
def db_session_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_multisig_approval_and_quorum_decay_lifecycle(db_session: Session, monkeypatch):
    session = db_session
    client = TestClient(app)
    app.dependency_overrides[get_session] = lambda: session

    monkeypatch.setattr(
        DisbursementService,
        "disburse",
        lambda destination, amount, narrative, external_id: DisbursementResult(
            success=True,
            transaction_id=f"tx_msig_{uuid.uuid4().hex[:8]}",
            provider=getattr(destination, "provider_name", "MTN Mobile Money"),
            amount=amount,
            account_number=getattr(destination, "account_number", "256700000000")
        )
    )

    now_ms = now_epoch_ms()

    # 1. Setup 3 Users: Admin (Alice), Treasurer (Bob), Recipient Member (Charlie)
    alice = User(id=uuid.uuid4(), phone_number="+256701000001", full_name="Alice Admin", fcm_token="tok_alice")
    bob = User(id=uuid.uuid4(), phone_number="+256701000002", full_name="Bob Treasurer", fcm_token="tok_bob")
    charlie = User(id=uuid.uuid4(), phone_number="+256701000003", full_name="Charlie Recipient", fcm_token="tok_charlie")
    session.add_all([alice, bob, charlie])
    session.commit()

    group_id = f"grp-msig-{uuid.uuid4().hex[:8]}"
    group = Group(
        group_id=group_id,
        name="Multi-Sig Test Circle",
        type="MERRY_GO_ROUND",
        payment_mode="OBLIGATION",
        created_by_user_id=alice.id,
        currency="UGX",
        member_count=3,
        status="ACTIVE",
        group_image_url="https://example.com/msig.png"
    )
    session.add(group)

    details = RotatingGroupDetails(
        group_id=group_id,
        contribution_amount=100000.0,
        payouts_per_cycle=1,
        number_of_cycles=3,
        collection_frequency_days=7,
        group_start_time=now_ms,
        payout_order_strategy="RANDOM",
        total_expected_pool_per_cycle=300000.0,
        current_cycle=1,
        auto_disburse_when_full=True,
        multi_sig_payout_approval=True, # MULTI-SIG ENABLED
        early_turn_security_hold_percentage=0.0,
        minimum_kyc_tier=1,
        require_guarantor=False,
        guarantor_default_action="NONE",
        allow_partial_payments=True,
        allow_advance_deposits=True
    )
    session.add(details)

    gov = GroupGovernanceSettings(
        group_id=group_id,
        require_multi_signature=True,
        multi_sig_required_approvals=2,
        enable_quorum_decay=True,
        quorum_decay_hours=48,
        quorum_decay_minimum_approvals=1
    )
    session.add(gov)

    wallet = GroupWallet(group_id=group_id, currency="UGX", pooled_funds=300000, prepaid_funds=0, reserve_funds=0)
    session.add(wallet)

    # Memberships: Alice is ADMIN, Bob is TREASURER, Charlie is regular MEMBER
    m1 = GroupMembership(membership_id=str(uuid.uuid4()), group_id=group_id, user_id=alice.id, role="ADMIN", payout_position=2, is_signer=True, status="ACTIVE")
    m2 = GroupMembership(membership_id=str(uuid.uuid4()), group_id=group_id, user_id=bob.id, role="TREASURER", payout_position=3, is_signer=True, status="ACTIVE")
    m3 = GroupMembership(membership_id=str(uuid.uuid4()), group_id=group_id, user_id=charlie.id, role="MEMBER", payout_position=1, is_signer=False, status="ACTIVE")
    session.add_all([m1, m2, m3])

    # Payout for Cycle 1 (Recipient is Charlie, pot 300,000 UGX)
    payout = GroupPayout(
        group_id=group_id,
        cycle_number=1,
        user_id=charlie.id,
        amount_expected=300000,
        amount_received=0,
        status="PENDING",
        payout_date=now_ms,
        created_at=now_ms
    )
    session.add(payout)
    session.commit()

    # -------------------------------------------------------------
    # 1. Payout Worker Gates Payout -> PENDING_MULTISIG_APPROVAL
    # -------------------------------------------------------------
    process_single_payout(session, payout, now_ms=now_ms)
    session.refresh(payout)
    assert payout.status == "PENDING_MULTISIG_APPROVAL"

    # -------------------------------------------------------------
    # 2. Check Multisig Status API (Screen 1 Dashboard)
    # -------------------------------------------------------------
    app.dependency_overrides[get_current_user] = lambda: alice
    status_resp = client.get(f"/api/v1/groups/rotating/{group_id}/payouts/{payout.id}/multisig-status")
    assert status_resp.status_code == 200
    st_data = status_resp.json()["data"]
    assert st_data["required_signatures"] == 2
    assert st_data["collected_signatures_count"] == 0
    assert st_data["is_quorum_reached"] is False
    assert st_data["can_current_user_sign"] is True
    assert st_data["tlqd"]["decay_enabled"] is True
    assert st_data["tlqd"]["decay_interval_hours"] == 48

    # -------------------------------------------------------------
    # 3. Signer 1 (Alice) Signs
    # -------------------------------------------------------------
    sign_resp = client.post(
        f"/api/v1/groups/rotating/{group_id}/payouts/{payout.id}/sign",
        json={"pin": "1234", "device_fingerprint": "DEV-ALICE-PIXEL8"}
    )
    assert sign_resp.status_code == 200
    s_data = sign_resp.json()["data"]
    assert s_data["collected_signatures"] == 1
    assert s_data["required_signatures"] == 2
    assert s_data["is_quorum_reached"] is False
    assert s_data["payout_status"] == "PENDING_MULTISIG_APPROVAL"

    # Pessimistic Idempotency: Alice cannot sign twice
    dup_resp = client.post(
        f"/api/v1/groups/rotating/{group_id}/payouts/{payout.id}/sign",
        json={"pin": "1234"}
    )
    assert dup_resp.status_code == 400
    assert "already signed" in dup_resp.json()["detail"]

    # -------------------------------------------------------------
    # 4. Non-Signer (Charlie) Cannot Sign
    # -------------------------------------------------------------
    app.dependency_overrides[get_current_user] = lambda: charlie
    charlie_sign_resp = client.post(f"/api/v1/groups/rotating/{group_id}/payouts/{payout.id}/sign")
    assert charlie_sign_resp.status_code == 403

    # -------------------------------------------------------------
    # 5. TEST TIME-LOCKED QUORUM DECAY (TLQD)
    # -------------------------------------------------------------
    # Scenario: Bob is offline/unresponsive.
    # At t = 24h: 24h < 48h, so decay should NOT trigger yet.
    time_24h = now_ms + (24 * 3600 * 1000)
    decay_res_24 = process_time_locked_quorum_decay(session, now_ms_override=time_24h)
    assert decay_res_24["processed_decays_count"] == 0
    session.refresh(payout)
    assert payout.status == "PENDING_MULTISIG_APPROVAL"

    # At t = 48h: Quorum decays from 2 to 1 (since decay floor = 1).
    # Since Alice has already signed (1 signature), quorum is now SATISFIED!
    time_49h = now_ms + (49 * 3600 * 1000)
    decay_res_49 = process_time_locked_quorum_decay(session, now_ms_override=time_49h)
    assert decay_res_49["processed_decays_count"] == 1
    session.refresh(payout)
    assert payout.status == "APPROVED_BY_DECAY"

    # Verify chat announcement was broadcast
    chat_notice = session.exec(
        select(GroupChatMessage).where(
            GroupChatMessage.group_id == group_id,
            GroupChatMessage.message_type == "SYSTEM_EVENT"
        )
    ).first()
    assert chat_notice is not None
    assert "Time-Locked Quorum Decay Activated" in chat_notice.message_text

    # -------------------------------------------------------------
    # 6. Execute Disbursement with APPROVED_BY_DECAY
    # -------------------------------------------------------------
    process_single_payout(session, payout, now_ms=time_49h)
    session.refresh(payout)
    assert payout.status == "COMPLETED"
    assert payout.amount_received == 300000

    app.dependency_overrides.clear()


def test_multisig_dispute_and_freeze(db_session: Session):
    session = db_session
    client = TestClient(app)
    app.dependency_overrides[get_session] = lambda: session

    now_ms = now_epoch_ms()

    alice = User(id=uuid.uuid4(), phone_number="+256701000010", full_name="Alice Admin", fcm_token="tok_1")
    bob = User(id=uuid.uuid4(), phone_number="+256701000020", full_name="Bob Treasurer", fcm_token="tok_2")
    session.add_all([alice, bob])
    session.commit()

    group_id = f"grp-veto-{uuid.uuid4().hex[:8]}"
    group = Group(group_id=group_id, name="Veto Chama", type="MERRY_GO_ROUND", payment_mode="OBLIGATION", created_by_user_id=alice.id, currency="UGX", member_count=2, status="ACTIVE", group_image_url="https://example.com/icon.png")
    session.add(group)

    m1 = GroupMembership(membership_id=str(uuid.uuid4()), group_id=group_id, user_id=alice.id, role="ADMIN", payout_position=1, is_signer=True, status="ACTIVE")
    m2 = GroupMembership(membership_id=str(uuid.uuid4()), group_id=group_id, user_id=bob.id, role="TREASURER", payout_position=2, is_signer=True, status="ACTIVE")
    session.add_all([m1, m2])

    payout = GroupPayout(group_id=group_id, cycle_number=1, user_id=alice.id, amount_expected=200000, amount_received=0, status="PENDING_MULTISIG_APPROVAL", payout_date=now_ms, created_at=now_ms)
    session.add(payout)
    session.commit()

    # Treasurer Bob inspects and vetoes the payout due to discrepancy
    app.dependency_overrides[get_current_user] = lambda: bob
    veto_resp = client.post(
        f"/api/v1/groups/rotating/{group_id}/payouts/{payout.id}/dispute",
        json={"reason": "Audit discrepancy: Member obligation records not fully settled."}
    )
    assert veto_resp.status_code == 200
    session.refresh(payout)
    assert payout.status == "FROZEN_DISPUTED"
    assert "Frozen by TREASURER Bob Treasurer" in payout.hold_reason

    # Subsequent signing attempts are blocked while frozen
    app.dependency_overrides[get_current_user] = lambda: alice
    sign_attempt = client.post(f"/api/v1/groups/rotating/{group_id}/payouts/{payout.id}/sign")
    assert sign_attempt.status_code == 400
    assert "frozen" in sign_attempt.json()["detail"].lower()

    # Quorum decay ignores frozen/disputed payouts
    time_100h = now_ms + (100 * 3600 * 1000)
    decay_res = process_time_locked_quorum_decay(session, now_ms_override=time_100h)
    assert decay_res["processed_decays_count"] == 0
    session.refresh(payout)
    assert payout.status == "FROZEN_DISPUTED"

    app.dependency_overrides.clear()
