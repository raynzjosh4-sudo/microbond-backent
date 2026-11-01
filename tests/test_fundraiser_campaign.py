import time
import uuid
import importlib
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.main import app
from app.models.user.user import User


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session, monkeypatch):
    # Disable live DB migrations and APScheduler during test startup
    monkeypatch.setattr("app.main.init_db", lambda: None)
    monkeypatch.setattr("app.main.start_scheduler", lambda: None)

    create_mod = importlib.import_module("app.api.routes.group.fundraiser.create_fundraiser")
    release_mod = importlib.import_module("app.api.routes.group.fundraiser.release_funds")
    deposit_mod = importlib.import_module("app.api.routes.group.deposit_pipeline.direct_deposit")

    monkeypatch.setattr(create_mod, "broadcast_system_message_sync", lambda **kwargs: None)
    monkeypatch.setattr(release_mod, "broadcast_system_message_sync", lambda **kwargs: None)
    monkeypatch.setattr(deposit_mod, "broadcast_system_message_sync", lambda **kwargs: None)
    monkeypatch.setattr(deposit_mod, "trigger_post_deposit_notifications", lambda **kwargs: None)

    async def mock_broadcast(*args, **kwargs):
        return None

    monkeypatch.setattr(deposit_mod.ws_manager, "broadcast_to_group", mock_broadcast)
    monkeypatch.setattr(release_mod.ws_manager, "broadcast_to_group", mock_broadcast)

    user_id = uuid.uuid4()
    test_user = User(
        id=user_id,
        phone_number="+256700000001",
        full_name="Fundraiser Organizer",
        kyc_tier=2,
        is_phone_verified=True,
    )
    session.add(test_user)
    session.commit()
    session.refresh(test_user)

    def get_session_override():
        return session

    def get_current_user_override():
        return test_user

    app.dependency_overrides[get_session] = get_session_override
    app.dependency_overrides[get_current_user] = get_current_user_override

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_create_and_query_fundraiser(client: TestClient):
    payload = {
        "name": "Community Hospital Relief",
        "description": "Emergency oxygen fund",
        "group_image_url": "https://example.com/hospital.png",
        "start_date": int(time.time() * 1000),
        "visibility": "PUBLIC",
        "currency": "UGX",
        "target_amount": 10000000,
        "campaign_deadline": int(time.time() * 1000) + 7 * 86400 * 1000,
        "payout_destination_type": "NOMINATED_ACCOUNT",
        "nominated_account_id": "acc-mtn-077123456",
        "payout_trigger_mode": "MANUAL",
        "require_multi_signoff": True,
        "signoff_count_required": 2,
    }
    create_res = client.post("/api/v1/groups/fundraiser/create", json=payload)
    assert create_res.status_code == 200, create_res.text
    group_id = create_res.json()["data"]["group_id"]

    dash_res = client.get(f"/api/v1/groups/fundraiser/{group_id}/dashboard")
    assert dash_res.status_code == 200
    dash_data = dash_res.json()["data"]
    assert dash_data["campaign_config"]["target_amount"] == 10000000
    assert dash_data["live_stats"]["total_raised"] == 0
    assert dash_data["live_stats"]["is_active"] is True
    assert dash_data["progress_percentage"] == 0.0

    settings_res = client.get(f"/api/v1/groups/fundraiser/{group_id}/settings")
    assert settings_res.status_code == 200
    assert settings_res.json()["data"]["live_stats"]["minimum_donation_amount"] == 500

    patch_res = client.patch(
        f"/api/v1/groups/fundraiser/{group_id}/settings",
        json={"minimum_donation_amount": 2000, "allow_overfunding": False},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["data"]["minimum_donation_amount"] == 2000
    assert patch_res.json()["data"]["allow_overfunding"] is False


def test_fundraiser_deposit_pipeline_validations(client: TestClient, session: Session):
    payload = {
        "name": "School Renovation Drive",
        "description": "New roofs for classrooms",
        "group_image_url": "https://example.com/school.png",
        "start_date": int(time.time() * 1000),
        "target_amount": 50000,
        "campaign_deadline": int(time.time() * 1000) + 86400 * 1000,
        "payout_destination_type": "NOMINATED_ACCOUNT",
        "nominated_account_id": "acc-bank-123",
        "payout_trigger_mode": "MANUAL",
        "require_multi_signoff": False,
        "signoff_count_required": 1,
    }
    create_res = client.post("/api/v1/groups/fundraiser/create", json=payload)
    assert create_res.status_code == 200
    group_id = create_res.json()["data"]["group_id"]

    # Configure minimum donation to 5,000 UGX, no overfunding, and stop on target reached
    client.patch(
        f"/api/v1/groups/fundraiser/{group_id}/settings",
        json={"minimum_donation_amount": 5000, "allow_overfunding": False, "stop_on_target_reached": True},
    )

    # 1. Attempt donation below minimum -> 400
    sub_min_res = client.post(
        f"/api/v1/groups/{group_id}/deposits/direct",
        json={"amount": 2000, "payment_method": "MTN_MOMO"},
    )
    assert sub_min_res.status_code == 400
    assert "Minimum donation" in sub_min_res.json()["detail"]

    # 2. Attempt donation exceeding target without overfunding -> 400
    over_res = client.post(
        f"/api/v1/groups/{group_id}/deposits/direct",
        json={"amount": 60000, "payment_method": "MTN_MOMO"},
    )
    assert over_res.status_code == 400
    assert "Overfunding is disabled" in over_res.json()["detail"]

    # 3. Valid donation meeting target exactly (50,000)
    valid_res = client.post(
        f"/api/v1/groups/{group_id}/deposits/direct",
        json={"amount": 50000, "payment_method": "MTN_MOMO"},
    )
    assert valid_res.status_code == 200
    assert valid_res.json()["status"] == "SUCCESS"

    # Verify live stats updated and auto-closed because stop_on_target_reached is True
    dash_res = client.get(f"/api/v1/groups/fundraiser/{group_id}/dashboard")
    assert dash_res.status_code == 200
    dash_data = dash_res.json()["data"]
    assert dash_data["live_stats"]["total_raised"] == 50000
    assert dash_data["live_stats"]["donor_count"] == 1
    assert dash_data["live_stats"]["is_active"] is False  # stop_on_target_reached flipped it
    assert dash_data["progress_percentage"] == 100.0

    # 4. Release funds
    rel_res = client.post(f"/api/v1/groups/fundraiser/{group_id}/release-funds")
    assert rel_res.status_code == 200
    assert rel_res.json()["data"]["total_released"] == 50000
