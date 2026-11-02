import uuid

import pytest
from fastapi import Depends, Request
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.main import app
from app.api.routes.group.chat.messages.helpers import messages_helpers
from app.models.group.group import Group, GroupMembership
from app.models.group.chat import GroupChatMessage
from app.models.group.report import GroupFinancialReport
from app.models.group.settings import GroupCommonSettings
from app.models.group.settings import GroupCommunicationSettings
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

    def authenticated_test_user(
        request: Request,
        test_session: Session = Depends(get_session),
    ) -> User:
        test_session.info["settings_announcement_context"] = {
            "group_id": request.path_params.get("group_id"),
            "method": request.method,
            "path": request.url.path,
            "actor_id": str(admin.id),
            "actor_name": admin.full_name,
        }
        test_session.info.pop("settings_announcement_pending", None)
        test_session.info.pop("settings_announcement_skip_tracker", None)
        return admin

    app.dependency_overrides[get_current_user] = authenticated_test_user
    client = TestClient(app)
    yield client, session, admin, group
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_current_user, None)
    session.close()
    engine.dispose()


def test_common_settings_can_be_read_and_partially_updated(
    common_settings_context, monkeypatch
):
    client, session, admin, group = common_settings_context

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
    assert all(message.sender_id == str(admin.id) for message in messages)
    messages_by_setting = {
        message.attachments[0]["setting"]: message for message in messages
    }
    assert "Group Admin changed minimum partial payment from Not set to UGX 1,000." in (
        messages_by_setting["minimum_partial_payment_amount"].message_text
    )
    assert "Partial payments below this amount will not be accepted." in (
        messages_by_setting["minimum_partial_payment_amount"].message_text
    )
    assert "Group Admin changed payment approval threshold from Not set to UGX 500,000." in (
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
        "Group Admin changed advance payments from Disabled to Enabled." in message.message_text
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


def test_settings_announcements_are_enabled_by_default_and_include_the_admin(
    common_settings_context, monkeypatch
):
    client, session, admin, group = common_settings_context
    websocket_events = []
    monkeypatch.setattr(
        messages_helpers,
        "notify_all_group_members_sync",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        messages_helpers.ws_manager,
        "broadcast_to_group_sync",
        lambda group_id, payload: websocket_events.append((group_id, payload)),
    )

    response = client.patch(
        f"/api/v1/groups/{group.group_id}/settings/privacy",
        json={"hide_total_group_balance": True},
    )
    assert response.status_code == 200, response.text

    messages = session.exec(
        select(GroupChatMessage).where(
            GroupChatMessage.group_id == group.group_id,
            GroupChatMessage.message_type == "SYSTEM_EVENT",
        )
    ).all()
    assert len(messages) == 1
    assert messages[0].sender_id == str(admin.id)
    assert "Group Admin changed group balance visibility from disabled to enabled." in (
        messages[0].message_text
    )
    assert messages[0].attachments[0]["setting"] == "hide_total_group_balance"
    assert len(websocket_events) == 1
    assert websocket_events[0][0] == group.group_id
    assert websocket_events[0][1]["message"]["sender_id"] == str(admin.id)


def test_disabling_system_announcements_suppresses_setting_messages(
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
    session.add(
        GroupCommunicationSettings(
            group_id=group.group_id,
            announce_system_events=False,
        )
    )
    session.commit()

    response = client.patch(
        f"/api/v1/groups/{group.group_id}/settings/milestones",
        json={"announce_system_events": True},
    )
    assert response.status_code == 200, response.text
    messages = session.exec(
        select(GroupChatMessage).where(
            GroupChatMessage.group_id == group.group_id,
            GroupChatMessage.message_type == "SYSTEM_EVENT",
        )
    ).all()
    assert len(messages) == 1
    assert messages[0].attachments[0]["setting"] == "announce_system_events"
    assert "Future group setting changes will be announced" in messages[0].message_text

    response = client.patch(
        f"/api/v1/groups/{group.group_id}/settings/milestones",
        json={"announce_system_events": False},
    )
    assert response.status_code == 200, response.text

    response = client.patch(
        f"/api/v1/groups/{group.group_id}/settings/privacy",
        json={"hide_total_group_balance": True},
    )
    assert response.status_code == 200, response.text
    messages = session.exec(
        select(GroupChatMessage).where(
            GroupChatMessage.group_id == group.group_id,
            GroupChatMessage.message_type == "SYSTEM_EVENT",
        )
    ).all()
    assert len(messages) == 1


def test_group_image_setting_announcement_includes_the_changed_image(
    common_settings_context, monkeypatch
):
    _, session, admin, group = common_settings_context
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
    session.info["settings_announcement_context"] = {
        "group_id": group.group_id,
        "method": "PATCH",
        "path": f"/api/v1/groups/{group.group_id}/settings/profile",
        "actor_id": str(admin.id),
        "actor_name": admin.full_name,
    }

    group.group_image_url = "https://cdn.example.com/groups/new-icon.png"
    session.add(group)
    session.commit()

    message = session.exec(
        select(GroupChatMessage).where(
            GroupChatMessage.group_id == group.group_id,
            GroupChatMessage.message_type == "SYSTEM_EVENT",
        )
    ).one()
    assert message.sender_id == str(admin.id)
    assert message.media_url == group.group_image_url
    assert message.media_type == "IMAGE"
    assert message.attachments[0]["setting"] == "group_image_url"


def test_report_visibility_changes_announce_exact_member_report_effects(
    common_settings_context, monkeypatch
):
    client, session, admin, group = common_settings_context
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
    fields = {
        "vis_report_expected_revenue": "expected revenue",
        "vis_report_actual_collection": "actual collections",
        "vis_report_deficit": "deficit tracking",
        "vis_report_reserve_fund": "reserve fund status",
        "vis_report_escrow_holds": "escrow holds",
    }

    response = client.patch(
        f"/api/v1/groups/{group.group_id}/settings/privacy",
        json={field: True for field in fields},
    )
    assert response.status_code == 200, response.text

    messages = session.exec(
        select(GroupChatMessage).where(
            GroupChatMessage.group_id == group.group_id,
            GroupChatMessage.message_type == "SYSTEM_EVENT",
        )
    ).all()
    assert len(messages) == len(fields)
    assert {message.attachments[0]["setting"] for message in messages} == set(fields)
    assert all(message.sender_id == str(admin.id) for message in messages)
    for message in messages:
        assert "from hidden to shown" in message.message_text
        assert f"Members can see {fields[message.attachments[0]['setting']]} on the report card." in message.message_text

    response = client.patch(
        f"/api/v1/groups/{group.group_id}/settings/privacy",
        json={"vis_report_actual_collection": False},
    )
    assert response.status_code == 200, response.text
    messages = session.exec(
        select(GroupChatMessage).where(
            GroupChatMessage.group_id == group.group_id,
            GroupChatMessage.message_type == "SYSTEM_EVENT",
        )
    ).all()
    hidden_message = next(
        message
        for message in messages
        if message.attachments[0]["setting"] == "vis_report_actual_collection"
        and "from shown to hidden" in message.message_text
    )
    assert "Actual collections are hidden from the member report card." in hidden_message.message_text


def test_member_visibility_toggle_is_announced_as_visibility_not_behavior(
    common_settings_context, monkeypatch
):
    client, session, admin, group = common_settings_context
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
    response = client.patch(
        f"/api/v1/groups/{group.group_id}/settings/member-visibility",
        json={"vis_announce_system_events": False},
    )
    assert response.status_code == 200, response.text

    message = session.exec(
        select(GroupChatMessage).where(
            GroupChatMessage.group_id == group.group_id,
            GroupChatMessage.message_type == "SYSTEM_EVENT",
        )
    ).one()
    assert message.sender_id == str(admin.id)
    assert message.attachments[0]["setting"] == "vis_announce_system_events"
    assert "system event announcements member visibility" in message.message_text
    assert "setting is now hidden from members" in message.message_text


def test_report_visibility_keys_drive_available_and_generated_sections(
    common_settings_context, monkeypatch
):
    client, session, admin, group = common_settings_context
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

    response = client.patch(
        f"/api/v1/groups/{group.group_id}/settings/member-visibility",
        json={
            "report_sections": {
                "week_summary": True,
                "member_balances": False,
                "members_who_saved": True,
                "payout_rotation": True,
            }
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["report_sections"] == {
        "week_summary": True,
        "daily_records": False,
        "member_balances": False,
        "members_who_saved": True,
        "members_who_missed": False,
        "payout_rotation": True,
        "group_activity": False,
        "contribution_history": False,
        "all_members": False,
    }

    response = client.get(
        f"/api/v1/groups/{group.group_id}/settings/member-visibility"
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["report_sections"]["member_balances"] is False
    assert response.json()["data"]["report_sections"]["members_who_saved"] is True

    response = client.get(
        f"/api/v1/groups/{group.group_id}/reports/available-sections"
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["viewer_role"] == "ADMIN"
    assert response.json()["data"]["group_type"] == "MERRY_GO_ROUND"
    admin_available = {
        section["key"] for section in response.json()["data"]["sections"]
    }
    assert "member_balances" in admin_available
    assert "payout_rotation" in admin_available
    assert response.json()["data"]["detail_visibility"]["vis_report_expected_revenue"] is False

    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group.group_id,
            GroupMembership.user_id == admin.id,
        )
    ).one()
    membership.role = "MEMBER"
    group.type = "GOAL_SAVINGS"
    session.add(group)
    session.add(membership)
    session.commit()

    response = client.get(
        f"/api/v1/groups/{group.group_id}/reports/available-sections"
    )
    assert response.status_code == 200, response.text
    available = {section["key"] for section in response.json()["data"]["sections"]}
    assert "member_balances" not in available
    assert "week_summary" in available
    assert "members_who_saved" in available
    assert "payout_rotation" not in available

    response = client.post(
        f"/api/v1/groups/{group.group_id}/reports",
        json={
            "included_sections": ["member_balances"],
            "period": {"type": "WEEK", "selected_date": "2026-10-05"},
        },
    )
    assert response.status_code == 403
    assert "member_balances" in response.json()["detail"]["keys"]

    response = client.post(
        f"/api/v1/groups/{group.group_id}/reports",
        json={
            "included_sections": ["week_summary", "members_who_saved"],
            "period": {"type": "WEEK", "selected_date": "2026-10-05"},
        },
    )
    assert response.status_code == 200, response.text
    generated_sections = response.json()["data"]["sections"]
    assert [section["key"] for section in generated_sections] == [
        "week_summary",
        "members_who_saved",
    ]
    assert response.json()["data"]["report_id"]
    stored_report = session.get(
        GroupFinancialReport,
        response.json()["data"]["report_id"],
    )
    assert stored_report.included_sections == ["week_summary", "members_who_saved"]
    assert stored_report.payload["week_summary"]["week_totals"]

    response = client.get(
        f"/api/v1/groups/{group.group_id}/reports/custom?days=7&target_date_ms=1791331200000"
    )
    assert response.status_code == 200, response.text
    legacy_report = response.json()
    assert "member_stats" not in legacy_report
    assert "balance_counts" not in legacy_report

    report_messages = session.exec(
        select(GroupChatMessage).where(
            GroupChatMessage.group_id == group.group_id,
            GroupChatMessage.message_type == "SYSTEM_EVENT",
        )
    ).all()
    section_messages = [
        message for message in report_messages
        if message.attachments
        and message.attachments[0].get("setting_type") == "REPORT_SECTION_VISIBILITY"
    ]
    assert {message.attachments[0]["setting"] for message in section_messages} == {
        "week_summary",
        "members_who_saved",
        "payout_rotation",
    }

    comm = GroupCommunicationSettings(group_id=group.group_id, announce_system_events=False)
    session.add(comm)
    membership.role = "ADMIN"
    session.add(membership)
    session.commit()
    response = client.patch(
        f"/api/v1/groups/{group.group_id}/settings/member-visibility",
        json={"report_sections": {"all_members": True}},
    )
    assert response.status_code == 200, response.text
    report_messages_after_disabled_switch = session.exec(
        select(GroupChatMessage).where(
            GroupChatMessage.group_id == group.group_id,
            GroupChatMessage.message_type == "SYSTEM_EVENT",
        )
    ).all()
    assert len(report_messages_after_disabled_switch) == len(report_messages)
