import uuid
import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.rotating import RotatingGroupDetails
from app.models.group.settings import GroupGovernanceSettings, GroupFinancialSettings


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


def test_rotating_group_creation_and_settings_lifecycle(db_session: Session, monkeypatch):
    import app.api.routes.group.chat.messages.helpers.messages_helpers as mh
    monkeypatch.setattr(mh, "notify_all_group_members", lambda **kwargs: None)

    admin_user = User(
        id=uuid.uuid4(),
        phone_number="+256704903741",
        full_name="Alice Admin",
        kyc_tier=3,
        trust_score=90,
        is_verified=True,
    )
    db_session.add(admin_user)
    db_session.commit()

    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: admin_user
    client = TestClient(app)

    # 1. Create Rotating Group with customized advanced settings
    payload = {
        "name": "Alpha Chama 2026",
        "description": "Weekly rotating pool with advanced security",
        "group_image_url": "https://example.com/chama.png",
        "type": "MERRY_GO_ROUND",
        "payment_mode": "OBLIGATION",
        "visibility": "PRIVATE",
        "currency": "UGX",
        "contribution_amount": 100000.0,
        "maximum_member_capacity": 10,
        "payouts_per_cycle": 1,
        "collection_frequency_days": 7,
        "group_start_time": 1792842962000,
        "payout_order_strategy": "Randomized by App",
        "minimum_kyc_tier": 2,
        "require_guarantor": True,
        "guarantor_default_action": "CHARGE_48H",
        "allow_partial_payments": False,
        "allow_advance_deposits": True,
        "enforce_payout_holds": True,
        "late_fee_amount": 5000.0,
        # New Advanced Settings
        "auto_disburse_when_full": True,
        "multi_sig_payout_approval": True,
        "allow_turn_swaps": True,
        "turn_swap_approval_mode": "ADMIN_APPROVAL_REQUIRED",
        "early_turn_security_hold_percentage": 15.0,
        "require_guarantors_for_early_turns_only": True,
        "auto_renew_cycle": True,
        "reverse_payout_order_on_renew": True,
        "reminder_lead_time_hours": 48,
        "enable_auto_debit_prompt": True,
    }

    create_resp = client.post("/api/v1/groups/rotating/create", json=payload)
    assert create_resp.status_code == 200, create_resp.text
    group_id = create_resp.json()["data"]["group_id"]

    # Verify DB records
    details = db_session.exec(
        select(RotatingGroupDetails).where(RotatingGroupDetails.group_id == group_id)
    ).first()
    assert details is not None
    assert details.auto_disburse_when_full is True
    assert details.multi_sig_payout_approval is True
    assert details.allow_turn_swaps is True
    assert details.turn_swap_approval_mode == "ADMIN_APPROVAL_REQUIRED"
    assert details.early_turn_security_hold_percentage == 15.0
    assert details.require_guarantors_for_early_turns_only is True
    assert details.auto_renew_cycle is True
    assert details.reverse_payout_order_on_renew is True
    assert details.reminder_lead_time_hours == 48
    assert details.enable_auto_debit_prompt is True

    gov = db_session.exec(
        select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group_id)
    ).first()
    assert gov is not None
    assert gov.require_multi_signature is True

    fin = db_session.exec(
        select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group_id)
    ).first()
    assert fin is not None
    assert fin.enforce_payout_holds is True

    # 2. Get Settings endpoint (Rotating specific)
    get_resp = client.get(f"/api/v1/groups/rotating/{group_id}/settings/rotating")
    assert get_resp.status_code == 200, get_resp.text
    get_data = get_resp.json()["data"]
    assert get_data["auto_disburse_when_full"] is True
    assert get_data["early_turn_security_hold_percentage"] == 15.0
    assert get_data["turn_swap_approval_mode"] == "ADMIN_APPROVAL_REQUIRED"
    assert get_data["reminder_lead_time_hours"] == 48

    # Also verify unified settings endpoint includes them in type_specific_settings
    unified_resp = client.get(f"/api/v1/groups/{group_id}/settings/summary")
    assert unified_resp.status_code == 200, unified_resp.text
    type_spec = unified_resp.json()["data"]["type_specific_settings"]
    assert type_spec["auto_disburse_when_full"] is True
    assert type_spec["early_turn_security_hold_percentage"] == 15.0
    assert type_spec["turn_swap_approval_mode"] == "ADMIN_APPROVAL_REQUIRED"

    # 3. Update Settings via PATCH
    patch_resp = client.patch(
        f"/api/v1/groups/rotating/{group_id}/settings/rotating",
        json={
            "early_turn_security_hold_percentage": 20.0,
            "turn_swap_approval_mode": "MUTUAL_CONSENT",
            "reminder_lead_time_hours": 12,
        }
    )
    assert patch_resp.status_code == 200, patch_resp.text
    patch_data = patch_resp.json()["data"]
    assert patch_data["early_turn_security_hold_percentage"] == 20.0
    assert patch_data["turn_swap_approval_mode"] == "MUTUAL_CONSENT"
    assert patch_data["reminder_lead_time_hours"] == 12

    # 4. Update Settings via the alias endpoints used by Mobile Client:
    # PATCH /api/v1/groups/{group_id}/rotating-details
    alias_patch_resp = client.patch(
        f"/api/v1/groups/{group_id}/rotating-details",
        json={
            "allow_partial_payments": True,
            "allow_advance_deposits": False,
            "enable_auto_debit_prompt": False,
            "collection_frequency_days": 9,
        }
    )
    assert alias_patch_resp.status_code == 200, alias_patch_resp.text
    alias_data = alias_patch_resp.json()["data"]
    assert alias_data["allow_partial_payments"] is True
    assert alias_data["allow_advance_deposits"] is False
    assert alias_data["enable_auto_debit_prompt"] is False
    assert alias_data["collection_frequency_days"] == 9

    app.dependency_overrides.clear()


def test_rotating_group_creation_minimal_and_string_enums(db_session: Session, monkeypatch):
    import app.api.routes.group.chat.messages.helpers.messages_helpers as mh
    monkeypatch.setattr(mh, "notify_all_group_members", lambda **kwargs: None)

    admin_user = User(
        id=uuid.uuid4(),
        phone_number="+256704903741",
        full_name="Alice Admin",
        kyc_tier=3,
        trust_score=90,
        is_verified=True,
    )
    db_session.add(admin_user)
    db_session.commit()

    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: admin_user
    client = TestClient(app)

    # Minimal payload without optional fields or nested risk controls
    minimal_payload = {
        "name": "Minimal Rotating",
        "type": "MERRY_GO_ROUND",
        "contribution_amount": 25000.0,
        "payouts_per_cycle": 1,
        "collection_frequency_days": 7,
        "payout_order_strategy": "RANDOMIZED",  # lowercase / uppercase variation
        "collection_time": 1740000000000,
    }

    create_resp = client.post("/api/v1/groups/rotating/create", json=minimal_payload)
    assert create_resp.status_code == 200, create_resp.text
    group_id = create_resp.json()["data"]["group_id"]
    assert group_id is not None

    details = db_session.exec(
        select(RotatingGroupDetails).where(RotatingGroupDetails.group_id == group_id)
    ).first()
    assert details is not None
    assert details.payout_order_strategy == "Randomized by App"
    assert details.collection_time == "1740000000000"

    app.dependency_overrides.clear()

