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
from app.models.group.settings import GroupGovernanceSettings

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

def test_group_permissions_endpoints(db_session: Session):
    admin_id = uuid.uuid4()
    admin_user = User(id=admin_id, phone_number="+256700000001", full_name="Admin User")
    db_session.add(admin_user)

    member_id = uuid.uuid4()
    member_user = User(id=member_id, phone_number="+256700000002", full_name="Regular Member")
    db_session.add(member_user)

    group_id = f"group_{uuid.uuid4().hex[:8]}"
    group = Group(group_id=group_id, name="Test Permission Group", group_image_url="", type="MERRY_GO_ROUND", payment_mode="OBLIGATION", created_by_user_id=admin_id)
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

    gov_settings = GroupGovernanceSettings(
        group_id=group_id,
        members_can_edit_settings=True,
        members_can_send_messages=True,
        members_can_invite_via_link=False,
        admins_must_approve_new_members=False,
        requires_admin_approval=False
    )
    db_session.add(gov_settings)
    db_session.commit()

    current_test_user = admin_user
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: current_test_user

    client = TestClient(app)

    # 1. GET permissions as ADMIN
    res = client.get(f"/api/v1/groups/{group_id}/settings/permissions")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["members_can_edit_settings"] is True
    assert data["members_can_send_messages"] is True
    assert data["members_can_invite_via_link"] is False
    assert data["admins_must_approve_new_members"] is False

    # 2. PATCH permissions as ADMIN
    patch_payload = {
        "members_can_edit_settings": False,
        "members_can_send_messages": False,
        "members_can_invite_via_link": True,
        "admins_must_approve_new_members": True
    }
    patch_res = client.patch(f"/api/v1/groups/{group_id}/settings/permissions", json=patch_payload)
    assert patch_res.status_code == 200
    patch_data = patch_res.json()["data"]
    assert patch_data["members_can_edit_settings"] is False
    assert patch_data["members_can_send_messages"] is False
    assert patch_data["members_can_invite_via_link"] is True
    assert patch_data["admins_must_approve_new_members"] is True

    # Verify underlying DB model
    db_session.refresh(gov_settings)
    assert gov_settings.members_can_edit_settings is False
    assert gov_settings.members_can_send_messages is False
    assert gov_settings.members_can_invite_via_link is True
    assert gov_settings.admins_must_approve_new_members is True
    assert gov_settings.requires_admin_approval is True

    # 3. GET permissions as regular member
    current_test_user = member_user
    app.dependency_overrides[get_current_user] = lambda: member_user

    res_member = client.get(f"/api/v1/groups/{group_id}/settings/permissions")
    assert res_member.status_code == 200
    assert res_member.json()["data"]["members_can_send_messages"] is False

    # 4. PATCH permissions as regular member (should be 403 Forbidden)
    forbidden_res = client.patch(f"/api/v1/groups/{group_id}/settings/permissions", json={"members_can_send_messages": True})
    assert forbidden_res.status_code == 403

    app.dependency_overrides.clear()
