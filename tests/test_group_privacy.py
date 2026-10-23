import uuid
import pytest
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupVisibilitySettings

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

def test_group_privacy_endpoints_and_enforcement(db_session: Session):
    admin_id = uuid.uuid4()
    admin_user = User(id=admin_id, phone_number="+256701111111", full_name="Admin Boss")
    db_session.add(admin_user)

    member_id = uuid.uuid4()
    member_user = User(id=member_id, phone_number="+256702222222", full_name="Regular Member")
    db_session.add(member_user)

    group_id = f"group_{uuid.uuid4().hex[:8]}"
    group = Group(
        group_id=group_id,
        name="BANKOK FANANCIAL GROUP",
        group_image_url="",
        type="MERRY_GO_ROUND",
        payment_mode="OBLIGATION",
        created_by_user_id=admin_id,
        invite_code="BNK12345",
        visibility="PUBLIC"
    )
    db_session.add(group)

    admin_membership = GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=group_id,
        user_id=admin_id,
        role="ADMIN",
        status="ACTIVE"
    )
    member_membership = GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=group_id,
        user_id=member_id,
        role="MEMBER",
        status="ACTIVE"
    )
    db_session.add(admin_membership)
    db_session.add(member_membership)

    vis_settings = GroupVisibilitySettings(
        group_id=group_id,
        hide_total_group_balance=False,
        hide_member_contact_info=True,
        invite_only_discoverability=True
    )
    db_session.add(vis_settings)
    db_session.commit()

    current_test_user = admin_user
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: current_test_user

    client = TestClient(app)

    # 1. GET privacy settings as ADMIN
    res = client.get(f"/api/v1/groups/{group_id}/settings/privacy")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["group_name"] == "BANKOK FANANCIAL GROUP"
    assert data["hide_total_group_balance"] is False
    assert data["hide_member_contact_info"] is True
    assert data["invite_only_discoverability"] is True

    # 2. Regular member can also GET privacy settings
    current_test_user = member_user
    app.dependency_overrides[get_current_user] = lambda: member_user

    res_member = client.get(f"/api/v1/groups/{group_id}/settings/privacy")
    assert res_member.status_code == 200
    assert res_member.json()["data"]["hide_member_contact_info"] is True

    # 3. Regular member CANNOT PATCH privacy settings (403 Forbidden)
    patch_attempt = client.patch(
        f"/api/v1/groups/{group_id}/settings/privacy",
        json={"hide_total_group_balance": True}
    )
    assert patch_attempt.status_code == 403

    # 4. Member roster respects hide_member_contact_info
    # When regular member fetches roster, admin's phone number should be masked
    roster_res = client.get(f"/api/v1/groups/{group_id}/members")
    assert roster_res.status_code == 200
    roster = roster_res.json()
    admin_entry = next(m for m in roster if m["user_id"] == str(admin_id))
    # Phone number should be masked (e.g., +25670 *** 111)
    assert "***" in admin_entry["phone_number"]

    # But member sees their own phone number unmasked
    member_entry = next(m for m in roster if m["user_id"] == str(member_id))
    assert member_entry["phone_number"] == "+256702222222"

    # 5. ADMIN updates privacy settings (Toggling hide_member_contact_info to False and hide_total_group_balance to True)
    current_test_user = admin_user
    app.dependency_overrides[get_current_user] = lambda: admin_user

    patch_res = client.patch(
        f"/api/v1/groups/{group_id}/settings/privacy",
        json={
            "hide_total_group_balance": True,
            "hide_member_contact_info": False,
            "invite_only_discoverability": False
        }
    )
    assert patch_res.status_code == 200
    updated_data = patch_res.json()["data"]
    assert updated_data["hide_total_group_balance"] is True
    assert updated_data["hide_member_contact_info"] is False
    assert updated_data["invite_only_discoverability"] is False

    # 6. Verify in DB
    db_session.refresh(vis_settings)
    assert vis_settings.hide_total_group_balance is True
    assert vis_settings.hide_member_contact_info is False
    assert vis_settings.invite_only_discoverability is False

    app.dependency_overrides.clear()
