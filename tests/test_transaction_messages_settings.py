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
from app.models.group.settings import GroupCommunicationSettings, GroupVisibilitySettings
from app.models.infrastructure import AuditEvent


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


def test_contribution_messages_settings_flow(db_session: Session):
    admin_id = uuid.uuid4()
    admin_user = User(id=admin_id, phone_number="+256701111222", full_name="Admin Boss")
    db_session.add(admin_user)

    member_id = uuid.uuid4()
    member_user = User(id=member_id, phone_number="+256703333444", full_name="Regular Member")
    db_session.add(member_user)

    group_id = f"group_{uuid.uuid4().hex[:8]}"
    group = Group(
        group_id=group_id,
        name="BANKOK FANANCIAL KEEPING",
        group_image_url="",
        type="GOAL_SAVINGS",
        payment_mode="VOLUNTARY",
        created_by_user_id=admin_id,
        currency="UGX",
        member_count=5,
        visibility="PRIVATE"
    )
    db_session.add(group)

    admin_membership = GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=group_id,
        user_id=admin_id,
        role="ADMIN",
        status="ACTIVE"
    )
    db_session.add(admin_membership)

    member_membership = GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=group_id,
        user_id=member_id,
        role="MEMBER",
        status="ACTIVE"
    )
    db_session.add(member_membership)

    comm = GroupCommunicationSettings(
        group_id=group_id,
        broadcast_individual_deposit_receipts=True,
        announce_payout_updates=False,
        show_transfer_receipts=False,
        announce_admin_transactions=False
    )
    db_session.add(comm)

    vis = GroupVisibilitySettings(
        group_id=group_id,
        vis_broadcast_individual_deposit_receipts=True,
        vis_announce_payout_updates=True,
        vis_show_transfer_receipts=True,
        vis_announce_admin_transactions=True
    )
    db_session.add(vis)
    db_session.commit()

    # 1. Test GET as Admin using /contribution-messages alias
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: admin_user

    client = TestClient(app)

    res = client.get(f"/api/v1/groups/{group_id}/settings/contribution-messages")
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["group_name"] == "BANKOK FANANCIAL KEEPING"
    assert data["group_type"] == "GOAL_SAVINGS"
    assert data["member_count"] == 5
    assert data["is_admin"] is True
    assert data["screen_title"] == "Contribution messages"
    assert data["header_members_display"] == "5 members · confirmed transactions"

    # Verify UI items matching the Android screenshot exactly
    items = data["items"]
    assert len(items) == 4
    assert items[0]["title"] == "Broadcast individual contribution receipts"
    assert items[0]["enabled"] is True
    assert items[0]["visible_to_members"] is True

    assert items[1]["title"] == "Announce approved withdrawal updates"
    assert items[1]["enabled"] is False

    assert items[2]["title"] == "Show transfer receipts"
    assert items[2]["enabled"] is False

    assert items[3]["title"] == "Announce admin transactions"
    assert items[3]["enabled"] is False

    # 2. Test PATCH as Admin to toggle values and visibility
    patch_res = client.patch(
        f"/api/v1/groups/{group_id}/settings/contribution-messages",
        json={
            "broadcast_individual_contribution_receipts": True,
            "announce_approved_withdrawal_updates": True,
            "show_transfer_receipts": True,
            "announce_admin_transactions": True,
            "vis_show_transfer_receipts": False
        }
    )
    assert patch_res.status_code == 200
    patch_data = patch_res.json()["data"]
    assert patch_data["announce_approved_withdrawal_updates"] is True
    assert patch_data["show_transfer_receipts"] is True
    assert patch_data["visibility_status"]["vis_show_transfer_receipts"] is False

    # 3. Test audit log entry was created
    audit = db_session.query(AuditEvent).filter(AuditEvent.action == "TRANSACTION_MESSAGES_SETTINGS_UPDATED").first()
    assert audit is not None
    assert audit.entity_id == group_id

    # 4. Test GET as regular member (hidden items filtered out)
    app.dependency_overrides[get_current_user] = lambda: member_user
    member_res = client.get(f"/api/v1/groups/{group_id}/settings/transaction-messages")
    assert member_res.status_code == 200
    member_items = member_res.json()["data"]["items"]
    # Since vis_show_transfer_receipts is False, it should be filtered out for members
    item_ids = [item["id"] for item in member_items]
    assert "show_transfer_receipts" not in item_ids
    assert "broadcast_individual_deposit_receipts" in item_ids

    # 5. Non-admin cannot patch
    forbidden_res = client.patch(
        f"/api/v1/groups/{group_id}/settings/contribution-messages",
        json={"broadcast_individual_deposit_receipts": False}
    )
    assert forbidden_res.status_code == 403

    app.dependency_overrides.clear()
