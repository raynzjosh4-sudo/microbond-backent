import uuid
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.user.userpaymentmethod.payment_method import UserPaymentMethod

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

def test_personal_membership_settings(db_session: Session):
    user_id = uuid.uuid4()
    user = User(id=user_id, phone_number="+256701234567", full_name="John Doe")
    db_session.add(user)

    pm = UserPaymentMethod(
        id="pm_mtn_123",
        user_id=user_id,
        provider_name="MTN Mobile Money",
        account_number="+2567012341234",
        is_default=True,
        is_verified=True
    )
    db_session.add(pm)

    group_id = f"group_{uuid.uuid4().hex[:8]}"
    group = Group(
        group_id=group_id,
        name="BANKOK FANANCIAL GROUP",
        group_image_url="",
        type="GOAL_SAVINGS",
        payment_mode="VOLUNTARY",
        created_by_user_id=user_id,
        currency="UGX",
        member_count=1,
        visibility="PRIVATE"
    )
    db_session.add(group)

    membership = GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=group_id,
        user_id=user_id,
        role="ADMIN",
        total_contributed=1800000,
        mute_notifications=False,
        include_chat_in_export=False,
        payment_method_id="pm_mtn_123"
    )
    db_session.add(membership)
    db_session.commit()

    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: user

    client = TestClient(app)

    # 1. GET personal settings (Screen 1)
    res = client.get(f"/api/v1/groups/{group_id}/membership/me")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["group_name"] == "BANKOK FANANCIAL GROUP"
    assert data["group_type_label"] == "Goal Savings"
    assert data["total_saved"] == 1800000
    assert "UGX 1,800,000" in data["total_saved_formatted"]
    assert data["mute_notifications"] is False
    assert data["notifications_label"] == "Off"
    assert data["payment_method"]["provider_name"] == "MTN Mobile Money"
    assert data["payment_method"]["masked_number"] == "**** 1234"

    # 2. PATCH personal settings (toggle mute, toggle include_chat_in_export)
    patch_res = client.patch(
        f"/api/v1/groups/{group_id}/membership/me",
        json={"mute_notifications": True, "include_chat_in_export": True}
    )
    assert patch_res.status_code == 200
    pdata = patch_res.json()["data"]
    assert pdata["mute_notifications"] is True
    assert pdata["include_chat_in_export"] is True

    # 3. Verify GET reflects new values
    res2 = client.get(f"/api/v1/groups/{group_id}/membership/me")
    assert res2.status_code == 200
    data2 = res2.json()["data"]
    assert data2["mute_notifications"] is True
    assert data2["notifications_label"] == "On"
    assert data2["include_chat_in_export"] is True

    app.dependency_overrides.clear()
