import uuid
import pytest
from datetime import datetime, timezone
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.finance import GroupPayout, MemberObligation, TurnSwapRequest, GuarantorPledge
from app.models.group.rotating import RotatingGroupDetails
from app.models.group.settings import GroupFinancialSettings, GroupGovernanceSettings
from app.models.group.wallet import GroupWallet
from app.cronjobs.finance.payout_disbursement_worker.process_single_payout import process_single_payout
from app.services.mobile_money.disbursement_service import DisbursementService, DisbursementResult


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


def test_payout_mechanics_enforcement(db_session: Session, monkeypatch):
    """Tests auto_disburse_when_full, multi_sig_payout_approval, early_turn_security_hold, and manual release."""
    # Mock disbursements
    monkeypatch.setattr(
        DisbursementService,
        "disburse",
        lambda **kwargs: DisbursementResult(
            success=True,
            transaction_id="mock_tx_123",
            provider="Airtel Money Uganda",
            amount=kwargs.get("amount", 180000),
            account_number="256700000002"
        )
    )
    import app.api.routes.group.chat.messages.helpers.messages_helpers as mh
    monkeypatch.setattr(mh, "notify_all_group_members", lambda **kwargs: None)

    # Create admin and members
    admin = User(id=uuid.uuid4(), phone_number="+256700000001", full_name="Admin Boss", kyc_tier=3, trust_score=100)
    member_1 = User(id=uuid.uuid4(), phone_number="+256700000002", full_name="Member One", kyc_tier=2, trust_score=80)
    member_2 = User(id=uuid.uuid4(), phone_number="+256700000003", full_name="Member Two", kyc_tier=2, trust_score=80)
    db_session.add_all([admin, member_1, member_2])
    db_session.commit()

    group_id = "test_rot_group_1"
    group = Group(
        group_id=group_id,
        name="Chama Circle",
        group_image_url="https://example.com/chama.png",
        type="MERRY_GO_ROUND",
        payment_mode="OBLIGATION",
        created_by_user_id=admin.id,
        status="ACTIVE"
    )
    wallet = GroupWallet(group_id=group_id, pooled_funds=2000000, reserve_funds=0, total_lifetime_payouts=0)
    rotating = RotatingGroupDetails(
        group_id=group_id,
        contribution_amount=100000.0,
        payouts_per_cycle=1,
        number_of_cycles=2,
        collection_frequency_days=7,
        group_start_time=1700000000000,
        payout_order_strategy="Randomized by App",
        total_expected_pool_per_cycle=200000.0,
        minimum_kyc_tier=1,
        require_guarantor=False,
        guarantor_default_action="NONE",
        allow_partial_payments=False,
        allow_advance_deposits=True,
        enforce_payout_holds=True,
        # Settings to test
        auto_disburse_when_full=False,
        multi_sig_payout_approval=True,
        early_turn_security_hold_percentage=10.0,
        auto_renew_cycle=True,
        reverse_payout_order_on_renew=True
    )
    admin_m = GroupMembership(membership_id=str(uuid.uuid4()), group_id=group_id, user_id=admin.id, role="ADMIN", status="ACTIVE")
    m1_m = GroupMembership(membership_id=str(uuid.uuid4()), group_id=group_id, user_id=member_1.id, role="MEMBER", status="ACTIVE")
    m2_m = GroupMembership(membership_id=str(uuid.uuid4()), group_id=group_id, user_id=member_2.id, role="MEMBER", status="ACTIVE")

    # Round 1 Payout for member_1
    payout_1 = GroupPayout(
        group_id=group_id,
        user_id=member_1.id,
        cycle_number=1,
        amount_expected=200000,
        amount_received=0,
        status="PENDING",
        payout_date=1700000000000
    )
    db_session.add_all([group, wallet, rotating, admin_m, m1_m, m2_m, payout_1])
    db_session.commit()

    now_ms = 1700000000000

    # 1. First run: multi_sig_payout_approval is True -> Should become PENDING_MULTISIG_APPROVAL
    process_single_payout(db_session, payout_1, now_ms=now_ms)
    assert payout_1.status == "PENDING_MULTISIG_APPROVAL"

    # 2. Sign multi-sig via API
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)

    sign_resp = client.post(f"/api/v1/groups/rotating/{group_id}/payouts/{payout_1.id}/sign")
    assert sign_resp.status_code == 200, sign_resp.text
    db_session.refresh(payout_1)
    assert payout_1.status == "APPROVED_FOR_DISBURSEMENT"

    # 3. Next worker run with auto_disburse_when_full=False:
    # Since it is approved, calling manual disburse API executes it
    disburse_resp = client.post(f"/api/v1/groups/rotating/{group_id}/payouts/{payout_1.id}/disburse")
    assert disburse_resp.status_code == 200, disburse_resp.text
    db_session.refresh(payout_1)
    db_session.refresh(wallet)

    assert payout_1.status == "COMPLETED"
    # Early turn security hold (10% of 200,000 = 20,000 withheld)
    assert payout_1.amount_received == 180000
    assert wallet.reserve_funds == 20000

    app.dependency_overrides.clear()


def test_turn_swap_admin_approval_mode(db_session: Session, monkeypatch):
    """Tests ADMIN_APPROVAL_REQUIRED mode gating turn swaps until admin signs off."""
    import app.api.routes.group.chat.messages.helpers.messages_helpers as mh
    monkeypatch.setattr(mh, "notify_all_group_members", lambda **kwargs: None)

    admin = User(id=uuid.uuid4(), phone_number="+256700000001", full_name="Admin Boss", kyc_tier=3, trust_score=100)
    user_a = User(id=uuid.uuid4(), phone_number="+256700000002", full_name="Alice", kyc_tier=2, trust_score=80)
    user_b = User(id=uuid.uuid4(), phone_number="+256700000003", full_name="Bob", kyc_tier=2, trust_score=80)
    db_session.add_all([admin, user_a, user_b])
    db_session.commit()

    group_id = "test_swap_group"
    group = Group(group_id=group_id, name="Swap Chama", group_image_url="https://example.com/chama.png", type="MERRY_GO_ROUND", payment_mode="OBLIGATION", created_by_user_id=admin.id, status="ACTIVE")
    rotating = RotatingGroupDetails(
        group_id=group_id,
        contribution_amount=50000.0,
        payouts_per_cycle=1,
        number_of_cycles=10,
        collection_frequency_days=7,
        group_start_time=1700000000000,
        payout_order_strategy="Fixed Roster",
        total_expected_pool_per_cycle=100000.0,
        minimum_kyc_tier=1,
        require_guarantor=False,
        guarantor_default_action="NONE",
        allow_partial_payments=False,
        allow_advance_deposits=True,
        enforce_payout_holds=True,
        allow_turn_swaps=True,
        turn_swap_approval_mode="ADMIN_APPROVAL_REQUIRED"
    )
    gov = GroupGovernanceSettings(group_id=group_id, allow_turn_swaps=True, turn_swap_approval_mode="ADMIN_APPROVAL_REQUIRED")
    admin_m = GroupMembership(membership_id=str(uuid.uuid4()), group_id=group_id, user_id=admin.id, role="ADMIN", status="ACTIVE")
    a_m = GroupMembership(membership_id=str(uuid.uuid4()), group_id=group_id, user_id=user_a.id, role="MEMBER", status="ACTIVE")
    b_m = GroupMembership(membership_id=str(uuid.uuid4()), group_id=group_id, user_id=user_b.id, role="MEMBER", status="ACTIVE")

    # Alice has Turn 3, Bob has Turn 7
    payout_a = GroupPayout(group_id=group_id, user_id=user_a.id, cycle_number=3, amount_expected=100000, status="PENDING", payout_date=1700000000000)
    payout_b = GroupPayout(group_id=group_id, user_id=user_b.id, cycle_number=7, amount_expected=100000, status="PENDING", payout_date=1700000000000)

    db_session.add_all([group, rotating, gov, admin_m, a_m, b_m, payout_a, payout_b])
    db_session.commit()

    app.dependency_overrides[get_session] = lambda: db_session
    client = TestClient(app)

    # 1. Alice requests swap with Bob
    app.dependency_overrides[get_current_user] = lambda: user_a
    req_resp = client.post(
        f"/api/v1/groups/{group_id}/swaps/request",
        json={"target_user_id": str(user_b.id)}
    )
    req_json = req_resp.json()
    swap_id = req_json.get("swap_request_id") or str(req_json.get("id"))

    # 2. Bob accepts the swap
    app.dependency_overrides[get_current_user] = lambda: user_b
    accept_resp = client.post(
        f"/api/v1/groups/{group_id}/swaps/{swap_id}/accept"
    )
    assert accept_resp.status_code == 200, accept_resp.text
    is_num = str(swap_id).isdigit()
    swap_record = db_session.exec(
        select(TurnSwapRequest).where(
            (TurnSwapRequest.swap_request_id == str(swap_id)) | (TurnSwapRequest.id == (int(swap_id) if is_num else -1))
        )
    ).first()
    # Status should be PENDING_ADMIN_APPROVAL because turn_swap_approval_mode is ADMIN_APPROVAL_REQUIRED
    assert swap_record is not None
    assert swap_record.status == "PENDING_ADMIN_APPROVAL"
    # Payouts should NOT be swapped yet
    db_session.refresh(payout_a)
    db_session.refresh(payout_b)
    assert payout_a.user_id == user_a.id
    assert payout_b.user_id == user_b.id

    # 3. Admin reviews and approves the swap
    app.dependency_overrides[get_current_user] = lambda: admin
    review_resp = client.post(
        f"/api/v1/groups/{group_id}/swaps/{swap_id}/admin-review",
        json={"action": "APPROVE"}
    )
    assert review_resp.status_code == 200, review_resp.text
    db_session.refresh(swap_record)
    assert swap_record.status == "ACCEPTED"

    # Now payouts ARE swapped!
    db_session.refresh(payout_a)
    db_session.refresh(payout_b)
    assert payout_a.user_id == user_b.id  # Bob now has Turn 3
    assert payout_b.user_id == user_a.id  # Alice now has Turn 7

    app.dependency_overrides.clear()
