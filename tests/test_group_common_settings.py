import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.main import app
from app.api.routes.group.chat.messages.helpers import messages_helpers
from app.models.group.group import Group, GroupMembership
from app.models.group.chat import GroupChatMessage
from app.models.group.settings import GroupCommonSettings
from app.models.user.user import User


@pytest.fixture
def common_settings_context():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    session = Session(engine)

    admin = User(
        id=uuid.uuid4(),
        phone_number="+256700000001",
        full_name="Group Admin",
    )
    group = Group(
        group_id="common-settings-group",
        name="Common Settings",
        group_image_url="",
        type="MERRY_GO_ROUND",
        payment_mode="OBLIGATION",
        created_by_user_id=admin.id,
    )
    membership = GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=group.group_id,
        user_id=admin.id,
        role="ADMIN",
        status="ACTIVE",
    )
    session.add(admin)
    session.add(group)
    session.add(membership)
    session.commit()

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: admin
    client = TestClient(app)
    yield client, session, admin, group
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_current_user, None)
    session.close()
    engine.dispose()


def test_common_settings_can_be_read_and_partially_updated(
    common_settings_context, monkeypatch
):
    client, session, _, group = common_settings_context

    monkeypatch.setattr(
        messages_helpers,
        "notify_all_group_members_sync",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        messages_helpers.ws_manager,
        "broadcast_to_group_sync",
        lambda *args, **kwargs: None,
    )

    response = client.get(f"/api/v1/groups/{group.group_id}/settings/common")
    assert response.status_code == 200, response.text
    initial_data = response.json()["data"]
    assert initial_data["minimum_kyc_tier"] == 1
    assert initial_data["maximum_member_capacity"] is None

    response = client.patch(
        f"/api/v1/groups/{group.group_id}/settings/common",
        json={
            "allow_partial_payments": True,
            "minimum_partial_payment_amount": 1000,
            "minimum_kyc_tier": 2,
            "group_start_time": 1792842962000,
            "require_guarantor": True,
            "maximum_member_capacity": 12,
            "collection_frequency_days": 7,
            "grace_period_hours": 48,
            "late_payment_policy": "STRIKE_AND_KEEP",
            "payment_approval_threshold": 500000,
            "allow_advance_payments": False,
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data == {
        "allow_partial_payments": True,
        "minimum_partial_payment_amount": 1000,
        "minimum_kyc_tier": 2,
        "group_start_time": 1792842962000,
        "require_guarantor": True,
        "maximum_member_capacity": 12,
        "collection_frequency_days": 7,
        "grace_period_hours": 48,
        "late_payment_policy": "STRIKE_AND_KEEP",
        "payment_approval_threshold": 500000,
        "allow_advance_payments": False,
    }

    stored = session.exec(
        select(GroupCommonSettings).where(
            GroupCommonSettings.group_id == group.group_id
        )
    ).one()
    assert stored.payment_approval_threshold == 500000
    session.refresh(group)
    assert group.max_members == 12

    messages = session.exec(
        select(GroupChatMessage).where(
            GroupChatMessage.group_id == group.group_id,
            GroupChatMessage.message_type == "SYSTEM_EVENT",
        )
    ).all()
    expected_changed_settings = {
        "allow_partial_payments",
        "minimum_partial_payment_amount",
        "minimum_kyc_tier",
        "group_start_time",
        "require_guarantor",
        "maximum_member_capacity",
        "collection_frequency_days",
        "grace_period_hours",
        "payment_approval_threshold",
        "allow_advance_payments",
    }
    assert len(messages) == len(expected_changed_settings)
    assert {message.group_id for message in messages} == {group.group_id}
    assert {message.attachments[0]["setting"] for message in messages} == expected_changed_settings
    assert all(message.sender_id == "SYSTEM" for message in messages)
    messages_by_setting = {
        message.attachments[0]["setting"]: message for message in messages
    }
    assert "Group Admin changed minimum partial payment to UGX 1,000." in (
        messages_by_setting["minimum_partial_payment_amount"].message_text
    )
    assert "Partial payments below this amount will not be accepted." in (
        messages_by_setting["minimum_partial_payment_amount"].message_text
    )
    assert "Group Admin changed payment approval threshold to UGX 500,000." in (
        messages_by_setting["payment_approval_threshold"].message_text
    )

    response = client.patch(
        f"/api/v1/groups/{group.group_id}/settings/common",
        json={"allow_advance_payments": True},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["allow_partial_payments"] is True
    assert response.json()["data"]["allow_advance_payments"] is True
    messages = session.exec(
        select(GroupChatMessage).where(
            GroupChatMessage.group_id == group.group_id,
            GroupChatMessage.message_type == "SYSTEM_EVENT",
        )
    ).all()
    assert len(messages) == len(expected_changed_settings) + 1
    advance_payment_messages = [
        message for message in messages
        if message.attachments[0]["setting"] == "allow_advance_payments"
    ]
    assert any(
        "Group Admin changed advance payments to Enabled." in message.message_text
        for message in advance_payment_messages
    )
    assert any(
        "Members can pay ahead" in message.message_text
        for message in advance_payment_messages
    )

    response = client.patch(
        f"/api/v1/groups/{group.group_id}/settings/common",
        json={"allow_advance_payments": True},
    )
    assert response.status_code == 200, response.text
    messages_after_no_op = session.exec(
        select(GroupChatMessage).where(
            GroupChatMessage.group_id == group.group_id,
            GroupChatMessage.message_type == "SYSTEM_EVENT",
        )
    ).all()
    assert len(messages_after_no_op) == len(messages)


def test_partial_payments_require_minimum_amount(common_settings_context):
    client, _, _, group = common_settings_context
    response = client.patch(
        f"/api/v1/groups/{group.group_id}/settings/common",
        json={"allow_partial_payments": True},
    )
    assert response.status_code == 422
    assert "minimum_partial_payment_amount is required" in response.json()["detail"]

    response = client.patch(
        f"/api/v1/groups/{group.group_id}/settings/common",
        json={
            "allow_partial_payments": True,
            "minimum_partial_payment_amount": 1000,
        },
    )
    assert response.status_code == 200, response.text

    response = client.patch(
        f"/api/v1/groups/{group.group_id}/settings/common",
        json={"minimum_partial_payment_amount": 0},
    )
    assert response.status_code == 422


def test_common_settings_require_admin_and_validate_policy(common_settings_context):
    client, _, admin, group = common_settings_context

    member = User(
        id=uuid.uuid4(),
        phone_number="+256700000002",
        full_name="Group Member",
    )
    client.app.dependency_overrides[get_current_user] = lambda: member
    response = client.patch(
        f"/api/v1/groups/{group.group_id}/settings/common",
        json={"grace_period_hours": 12},
    )
    assert response.status_code == 403

    client.app.dependency_overrides[get_current_user] = lambda: admin
    response = client.patch(
        f"/api/v1/groups/{group.group_id}/settings/common",
        json={"minimum_kyc_tier": 4},
    )
    assert response.status_code == 422
    response = client.patch(
        f"/api/v1/groups/{group.group_id}/settings/common",
        json={"late_payment_policy": "UNKNOWN"},
    )
    assert response.status_code == 422
