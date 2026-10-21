"""Integration tests for /analytics/catalog and /analytics/series endpoints using FastAPI TestClient."""
import uuid
from datetime import datetime
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlmodel import Session, select
import pytest

from app.main import app
from app.core.database import engine, get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.services.analytics.buckets import LOCAL_TZ

def ms(y, m, d, h=0, mi=0):
    return int(datetime(y, m, d, h, mi, tzinfo=LOCAL_TZ).timestamp() * 1000)

@pytest.fixture(name="client", scope="module")
def client_fixture():
    test_user_id = uuid.uuid4()
    test_phone = f"+2567{str(uuid.uuid4().int)[:8]}"
    test_user = User(
        id=test_user_id,
        phone_number=test_phone,
        full_name="Chart Test User",
        kyc_tier=2
    )

    with Session(engine) as session:
        session.add(test_user)
        session.commit()
        session.refresh(test_user)

        # Create a test group
        group_id = str(uuid.uuid4())
        group = Group(
            group_id=group_id,
            name="Analytics Test Group",
            group_image_url="https://example.com/group.png",
            payment_mode="OBLIGATION",
            type="MERRY_GO_ROUND",
            created_by_user_id=test_user_id
        )
        session.add(group)
        # Create membership
        membership = GroupMembership(
            membership_id=str(uuid.uuid4()),
            group_id=group_id,
            user_id=test_user_id,
            role="ADMIN",
            status="ACTIVE",
            joined_at=ms(2026, 9, 1)
        )
        session.add(membership)
        session.commit()

    def override_get_current_user(session: Session = Depends(get_session)):
        return session.get(User, test_user_id)

    app.dependency_overrides[get_current_user] = override_get_current_user
    client = TestClient(app)
    yield client, group_id
    app.dependency_overrides.clear()

def test_catalog_endpoint(client):
    client, group_id = client
    response = client.get(f"/api/v1/groups/{group_id}/analytics/catalog")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "metrics" in data
    assert len(data["metrics"]) >= 20

    metric_ids = [m["id"] for m in data["metrics"]]
    assert "successful_save_days" in metric_ids
    assert "daily_saving" in metric_ids
    assert "total_accumulation" in metric_ids
    assert "active_members" in metric_ids
    assert "payouts_completed" in metric_ids

def test_series_arbitrary_days_and_bucket(client):
    client, group_id = client
    # Request 38 days of data with 4-day buckets!
    response = client.get(
        f"/api/v1/groups/{group_id}/analytics/series",
        params={
            "y": "successful_save_days",
            "x": "time",
            "days": 38,
            "bucket_days": 4
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["meta"]["bucket_days"] == 4
    assert len(data["points"]) == 10  # 38 / 4 = 9.5 -> 10 buckets
    for point in data["points"]:
        assert "x" in point
        assert "y" in point
        assert "label" in point

def test_series_metric_vs_metric(client):
    client, group_id = client
    # Compare active_members (x) vs daily_saving (y)
    response = client.get(
        f"/api/v1/groups/{group_id}/analytics/series",
        params={
            "y": "daily_saving",
            "x": "active_members",
            "days": 30,
            "bucket_days": 7
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["meta"]["x"] == "active_members"
    assert data["meta"]["y"] == "daily_saving"
    for point in data["points"]:
        assert isinstance(point["x"], (int, float))
        assert isinstance(point["y"], (int, float))
