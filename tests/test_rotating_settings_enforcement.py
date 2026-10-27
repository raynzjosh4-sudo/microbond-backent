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
        # Settings to test
        auto_disburse_when_full=False,
        multi_sig_payout_approval=True,
        early_turn_security_hold_percentage=10.0,
        auto_renew_cycle=True,
        reverse_payout_order_on_renew=True
    )
    fin_settings = GroupFinancialSettings(group_id=group_id, enforce_payout_holds=True)
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
    db_session.add_all([group, wallet, rotating, fin_settings, admin_m, m1_m, m2_m, payout_1])
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
        allow_turn_swaps=True,
        turn_swap_approval_mode="ADMIN_APPROVAL_REQUIRED"
    )
    fin = GroupFinancialSettings(group_id=group_id, enforce_payout_holds=True)
    gov = GroupGovernanceSettings(group_id=group_id)
    admin_m = GroupMembership(membership_id=str(uuid.uuid4()), group_id=group_id, user_id=admin.id, role="ADMIN", status="ACTIVE")
    a_m = GroupMembership(membership_id=str(uuid.uuid4()), group_id=group_id, user_id=user_a.id, role="MEMBER", status="ACTIVE")
    b_m = GroupMembership(membership_id=str(uuid.uuid4()), group_id=group_id, user_id=user_b.id, role="MEMBER", status="ACTIVE")

    # Alice has Turn 3, Bob has Turn 7
    payout_a = GroupPayout(group_id=group_id, user_id=user_a.id, cycle_number=3, amount_expected=100000, status="PENDING", payout_date=1700000000000)
    payout_b = GroupPayout(group_id=group_id, user_id=user_b.id, cycle_number=7, amount_expected=100000, status="PENDING", payout_date=1700000000000)

    db_session.add_all([group, rotating, fin, gov, admin_m, a_m, b_m, payout_a, payout_b])
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


def test_rotating_contribution_amount_and_saving_days_lifecycle(db_session: Session, monkeypatch):
    """
    Tests the complete lifecycle of contribution_amount & saving_days_per_cycle:
    1. Nullable defaults on draft creation.
    2. Launch gate rejection when contribution_amount or saving_days_per_cycle is null.
    3. Proper pool calculation: pool = contribution_amount * saving_days * members.
    4. Successful launch locking the terms and activating cycle 1.
    5. Post-deposit lock prevention.
    """
    import app.api.routes.group.chat.messages.helpers.messages_helpers as mh
    monkeypatch.setattr(mh, "notify_all_group_members", lambda **kwargs: None)

    admin = User(id=uuid.uuid4(), phone_number="+256701111111", full_name="Admin Chief", kyc_tier=3, trust_score=100)
    member = User(id=uuid.uuid4(), phone_number="+256702222222", full_name="Member Saver", kyc_tier=2, trust_score=85)
    db_session.add_all([admin, member])
    db_session.commit()

    group_id = "rot_cycle_test_group"
    group = Group(
        group_id=group_id,
        name="Daily Accumulation Chama",
        group_image_url="https://example.com/chama.png",
        type="MERRY_GO_ROUND",
        payment_mode="OBLIGATION",
        created_by_user_id=admin.id,
        status="PENDING",
        max_members=2
    )
    wallet = GroupWallet(group_id=group_id, pooled_funds=0, reserve_funds=0, total_lifetime_payouts=0)
    # Draft group with NULL contribution_amount and NULL saving_days_per_cycle
    rotating = RotatingGroupDetails(
        group_id=group_id,
        contribution_amount=None,
        saving_days_per_cycle=None,
        payouts_per_cycle=1,
        number_of_cycles=2,
        collection_frequency_days=1,
        payout_order_strategy="Fixed Roster",
        total_expected_pool_per_cycle=None,
        minimum_kyc_tier=1,
        require_guarantor=False,
        guarantor_default_action="NONE",
        allow_partial_payments=False,
        allow_advance_deposits=True,
        is_payout_order_locked=False
    )
    fin_settings = GroupFinancialSettings(group_id=group_id, enforce_payout_holds=False)
    admin_m = GroupMembership(membership_id=str(uuid.uuid4()), group_id=group_id, user_id=admin.id, role="ADMIN", status="ACTIVE")
    member_m = GroupMembership(membership_id=str(uuid.uuid4()), group_id=group_id, user_id=member.id, role="MEMBER", status="ACTIVE")

    db_session.add_all([group, wallet, rotating, fin_settings, admin_m, member_m])
    db_session.commit()

    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)

    # 1. GET settings - verify nulls
    get_resp = client.get(f"/api/v1/groups/rotating/{group_id}/settings")
    assert get_resp.status_code == 200, get_resp.text
    data = get_resp.json()["data"]
    assert data["contribution_amount"] is None
    assert data["saving_days_per_cycle"] is None
    assert data["total_expected_pool_per_cycle"] is None

    # 2. Attempt to launch group while contribution_amount is null -> REJECTED
    launch_resp = client.post(f"/api/v1/groups/rotating/{group_id}/launch")
    assert launch_resp.status_code == 400
    assert "Contribution amount has not been configured" in launch_resp.json()["detail"]

    # 3. Update contribution_amount to 5,000 UGX
    patch_resp_1 = client.patch(
        f"/api/v1/groups/rotating/{group_id}/settings",
        json={"contribution_amount": 5000.0}
    )
    assert patch_resp_1.status_code == 200, patch_resp_1.text
    assert patch_resp_1.json()["data"]["contribution_amount"] == 5000.0

    # 4. Attempt to launch while saving_days_per_cycle is still null -> REJECTED
    launch_resp_2 = client.post(f"/api/v1/groups/rotating/{group_id}/launch")
    assert launch_resp_2.status_code == 400
    assert "Saving days per cycle has not been configured" in launch_resp_2.json()["detail"]

    # 5. Update saving_days_per_cycle to 9 days
    patch_resp_2 = client.patch(
        f"/api/v1/groups/rotating/{group_id}/settings",
        json={"saving_days_per_cycle": 9}
    )
    assert patch_resp_2.status_code == 200, patch_resp_2.text
    patch_data = patch_resp_2.json()["data"]
    assert patch_data["saving_days_per_cycle"] == 9
    # Pool: 5000 UGX/day * 9 days * 2 members = 90,000 UGX
    assert patch_data["total_expected_pool_per_cycle"] == 90000.0

    # 6. Admin launches group -> SUCCESS
    launch_resp_3 = client.post(f"/api/v1/groups/rotating/{group_id}/launch")
    assert launch_resp_3.status_code == 200, launch_resp_3.text
    launch_data = launch_resp_3.json()["data"]
    assert launch_data["status"] == "ACTIVE"
    assert launch_data["is_payout_order_locked"] is True
    assert launch_data["current_saving_day"] == 1
    assert launch_data["total_expected_pool_per_cycle"] == 90000.0

    # 7. Check obligations were generated with amount_due = 5000
    ob = db_session.exec(select(MemberObligation).where(MemberObligation.group_id == group_id)).first()
    assert ob is not None
    assert ob.amount_due == 5000.0

    # 8. Check GET settings reflects locked state and provides clear lock reason
    get_locked = client.get(f"/api/v1/groups/rotating/{group_id}/settings")
    assert get_locked.status_code == 200
    locked_data = get_locked.json()["data"]
    assert locked_data["is_cycle_active"] is True
    assert locked_data["is_financial_editable"] is False
    assert "Cycle 1 is currently active" in locked_data["edit_lock_reason"]

    # 9. Admin attempts to edit contribution_amount while cycle is on -> REJECTED with explanatory message
    patch_blocked = client.patch(
        f"/api/v1/groups/rotating/{group_id}/settings",
        json={"contribution_amount": 10000.0}
    )
    assert patch_blocked.status_code == 400
    detail = patch_blocked.json()["detail"]
    assert "Cycle 1 is currently active" in detail
    assert "locked to protect member deposits" in detail

    # 10. Admin attempts to edit saving_days_per_cycle while cycle is on -> ALSO REJECTED with message
    patch_blocked_days = client.patch(
        f"/api/v1/groups/rotating/{group_id}/settings",
        json={"saving_days_per_cycle": 14}
    )
    assert patch_blocked_days.status_code == 400
    assert "Cycle 1 is currently active" in patch_blocked_days.json()["detail"]

    # 11. Admin attempts to edit collection_frequency_days while cycle is on -> REJECTED
    patch_blocked_freq = client.patch(
        f"/api/v1/groups/rotating/{group_id}/settings",
        json={"collection_frequency_days": 7}
    )
    assert patch_blocked_freq.status_code == 400
    assert "collection frequency days" in patch_blocked_freq.json()["detail"].lower()
    assert "Cycle 1 is currently active" in patch_blocked_freq.json()["detail"]

    # 12. Admin attempts to edit collection_time while cycle is on -> REJECTED
    patch_blocked_time = client.patch(
        f"/api/v1/groups/rotating/{group_id}/settings",
        json={"collection_time": "12:00"}
    )
    assert patch_blocked_time.status_code == 400
    assert "collection time" in patch_blocked_time.json()["detail"].lower()

    # 13. Allowed mid-cycle settings (turn swaps, guarantors, KYC, partial, advance deposits, late fees, grace period) -> SUCCEED!
    patch_allowed = client.patch(
        f"/api/v1/groups/rotating/{group_id}/settings",
        json={
            "allow_turn_swaps": True,
            "turn_swap_approval_mode": "ADMIN_APPROVAL_REQUIRED",
            "require_guarantor": True,
            "minimum_kyc_tier": 2,
            "allow_partial_payments": True,
            "allow_advance_deposits": True,
            "late_fee_amount": 2500.0,
            "grace_period_hours": 48
        }
    )
    assert patch_allowed.status_code == 200, patch_allowed.text
    allowed_data = patch_allowed.json()["data"]
    assert allowed_data["allow_turn_swaps"] is True
    assert allowed_data["turn_swap_approval_mode"] == "ADMIN_APPROVAL_REQUIRED"
    assert allowed_data["require_guarantor"] is True
    assert allowed_data["allow_partial_payments"] is True
    assert allowed_data["allow_advance_deposits"] is True
    assert allowed_data["late_fee_amount"] == 2500.0
    assert allowed_data["grace_period_hours"] == 48

    app.dependency_overrides.clear()

