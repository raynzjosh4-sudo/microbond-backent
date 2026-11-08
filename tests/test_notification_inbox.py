import uuid
import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.dependencies import get_current_user
from app.api.routes.user.general.notifications import router
from app.core.database import get_session
from app.models.user.notification import Notification
from app.models.user.notification import NotificationReply
from app.models.group.group import Group, GroupMembership
from app.models.user.user import User


@pytest.fixture
def notification_context(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Group.__table__,
            GroupMembership.__table__,
            Notification.__table__,
            NotificationReply.__table__,
        ],
    )
    session = Session(engine)
    owner = User(phone_number="+256700000001", full_name="Inbox Owner")
    actor = User(phone_number="+256700000002", full_name="Sender")
    other_user = User(phone_number="+256700000003", full_name="Other User")
    session.add_all([owner, actor, other_user])
    session.commit()
    session.refresh(owner)
    session.refresh(actor)
    session.refresh(other_user)

    notification = Notification(
        recipient_user_id=owner.id,
        actor_user_id=actor.id,
        event_type="chat_message",
        category="messages",
        title="New message from Sender",
        preview="Hello there",
        body="Hello there, this is the full message.",
        source_type="group_chat_message",
        source_id=str(uuid.uuid4()),
        payload={"type": "chat_message"},
        can_reply=True,
    )
    session.add(notification)
    session.commit()
    session.refresh(notification)

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: owner
    client = TestClient(app)
    monkeypatch.setattr("app.services.notification_delivery.engine", engine)

    yield client, session, owner, actor, other_user, notification

    app.dependency_overrides.clear()
    session.close()
    engine.dispose()


def test_notification_list_detail_read_and_replies(notification_context):
    client, session, owner, actor, _, notification = notification_context

    response = client.get("/api/v1/users/me/notifications")
    assert response.status_code == 200
    assert response.json()["unread_count"] == 1
    assert response.json()["items"][0]["preview"] == "Hello there"

    response = client.get(f"/api/v1/users/me/notifications/{notification.id}")
    assert response.status_code == 200
    assert response.json()["body"] == "Hello there, this is the full message."
    assert response.json()["read_at"] is not None

    response = client.post(
        f"/api/v1/users/me/notifications/{notification.id}/replies",
        json={"body": "Thanks for the update."},
    )
    assert response.status_code == 201
    reply_id = response.json()["id"]

    response = client.get(f"/api/v1/users/me/notifications/{notification.id}")
    assert response.status_code == 200
    assert response.json()["replies"][0]["id"] == reply_id
    assert response.json()["replies"][0]["sender_user_id"] == str(owner.id)
    assert session.get(Notification, notification.id).read_at is not None
    reply_alert = session.exec(
        select(Notification).where(
            Notification.recipient_user_id == actor.id,
            Notification.event_type == "notification_reply",
        )
    ).first()
    assert reply_alert is not None
    assert reply_alert.payload["notification_id"] == str(notification.id)

    response = client.get("/api/v1/users/me/notifications")
    assert response.json()["unread_count"] == 0

    second_notification = Notification(
        recipient_user_id=owner.id,
        event_type="payment_completed",
        category="transactions",
        title="Payment complete",
        body="Your payment was received.",
        payload={},
    )
    session.add(second_notification)
    session.commit()
    response = client.post("/api/v1/users/me/notifications/read-all")
    assert response.status_code == 200
    assert response.json()["updated_count"] == 1
    assert session.get(Notification, second_notification.id).read_at is not None


def test_notification_access_is_scoped_to_authenticated_user(notification_context):
    client, session, _, _, other_user, notification = notification_context
    client.app.dependency_overrides[get_current_user] = lambda: other_user

    response = client.get(f"/api/v1/users/me/notifications/{notification.id}")
    assert response.status_code == 404

    response = client.delete(
        f"/api/v1/users/me/notifications/{notification.id}"
    )
    assert response.status_code == 404
    assert session.get(Notification, notification.id) is not None

    response = client.post(
        f"/api/v1/users/me/notifications/{notification.id}/replies",
        json={"body": "Unauthorized reply"},
    )
    assert response.status_code == 404


def test_notification_recipient_can_delete_notification_and_replies(
    notification_context,
):
    client, session, owner, actor, _, notification = notification_context
    reply = NotificationReply(
        notification_id=notification.id,
        sender_user_id=actor.id,
        body="Original reply",
    )
    session.add(reply)
    session.commit()
    session.refresh(reply)
    nested_reply = NotificationReply(
        notification_id=notification.id,
        sender_user_id=owner.id,
        parent_reply_id=reply.id,
        body="Nested reply",
    )
    session.add(nested_reply)
    session.commit()
    reply_ids = [reply.id, nested_reply.id]

    response = client.delete(
        f"/api/v1/users/me/notifications/{notification.id}"
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "message": "Notification deleted.",
    }
    assert session.get(Notification, notification.id) is None
    assert all(session.get(NotificationReply, reply_id) is None for reply_id in reply_ids)


def test_notification_actor_can_view_and_reply_without_marking_recipient_read(
    notification_context,
):
    client, session, _, actor, _, notification = notification_context
    client.app.dependency_overrides[get_current_user] = lambda: actor

    response = client.get(f"/api/v1/users/me/notifications/{notification.id}")
    assert response.status_code == 200
    assert response.json()["read_at"] is None
    response = client.patch(
        f"/api/v1/users/me/notifications/{notification.id}/read"
    )
    assert response.status_code == 404

    response = client.post(
        f"/api/v1/users/me/notifications/{notification.id}/replies",
        json={"body": "Thanks for letting me know."},
    )
    assert response.status_code == 201
    assert response.json()["body"] == "Thanks for letting me know."

    reply_alert = session.exec(
        select(Notification).where(
            Notification.recipient_user_id != actor.id,
            Notification.event_type == "notification_reply",
        )
    ).first()
    assert reply_alert is not None
    assert reply_alert.payload["notification_id"] == str(notification.id)
    assert session.get(Notification, notification.id).read_at is None


def test_push_notifications_are_persisted_once_per_user(notification_context):
    _, session, owner, actor, _, _ = notification_context
    owner.fcm_token = "test-token"
    session.add(owner)
    session.commit()

    from app.services.notification_delivery import record_push_notification

    message_id = str(uuid.uuid4())
    data = {
        "type": "chat_message",
        "message_id": message_id,
        "actor_id": str(actor.id),
        "can_reply": "true",
    }
    record_push_notification("test-token", "New message", "A message", data)
    record_push_notification("test-token", "New message", "A message", data)

    stored = session.exec(
        select(Notification).where(Notification.source_id == message_id)
    ).all()
    assert len(stored) == 1
    assert stored[0].can_reply is True
    assert stored[0].recipient_user_id == owner.id


def test_notification_is_saved_without_an_fcm_token(notification_context):
    _, session, owner, _, _, _ = notification_context

    from app.services.notification_delivery import create_notifications_for_users

    deposit_id = str(uuid.uuid4())
    create_notifications_for_users(
        [owner.id],
        "Deposit received",
        "UGX 25,000 was added to your group.",
        {"type": "deposit_received", "deposit_id": deposit_id},
    )

    stored = session.exec(
        select(Notification).where(Notification.source_id == deposit_id)
    ).first()
    assert stored is not None
    assert stored.category == "transactions"
    assert owner.fcm_token is None


def test_group_filter_and_unread_count_only_include_selected_group(
    notification_context,
):
    client, session, owner, _, _, notification = notification_context
    notification.group_id = "group-one"
    session.add(notification)
    session.add(
        Notification(
            recipient_user_id=owner.id,
            event_type="deposit_broadcast",
            category="transactions",
            title="Deposit in another group",
            body="A separate group deposit.",
            group_id="group-two",
            payload={},
        )
    )
    session.commit()

    response = client.get(
        "/api/v1/users/me/notifications",
        params={"group_id": "group-one", "unread_only": "true"},
    )
    assert response.status_code == 200
    assert response.json()["unread_count"] == 1
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["group_id"] == "group-one"

    response = client.post(
        "/api/v1/users/me/notifications/read-all",
        params={"group_id": "group-one"},
    )
    assert response.status_code == 200
    assert response.json()["updated_count"] == 1
    assert session.exec(
        select(Notification).where(
            Notification.recipient_user_id == owner.id,
            Notification.group_id == "group-two",
            Notification.read_at.is_(None),
        )
    ).first()


def test_group_deposit_notification_includes_depositor_and_members(
    notification_context,
    monkeypatch,
):
    _, session, owner, actor, other_user, _ = notification_context
    group_id = "deposit-notification-group"
    session.add(
        Group(
            group_id=group_id,
            name="Deposit Group",
            group_image_url="",
            type="MERRY_GO_ROUND",
            payment_mode="OBLIGATION",
            created_by_user_id=owner.id,
        )
    )
    session.add_all(
        [
            GroupMembership(
                membership_id=str(uuid.uuid4()),
                group_id=group_id,
                user_id=user.id,
                role="MEMBER",
                status="ACTIVE",
            )
            for user in (owner, actor, other_user)
        ]
    )
    session.commit()

    import app.services.push_notifications as push_module

    monkeypatch.setattr(push_module, "engine", session.get_bind())
    monkeypatch.setattr(push_module, "send_push_notification", lambda *args: True)
    transaction_id = str(uuid.uuid4())
    data = {
        "type": "DEPOSIT_BROADCAST",
        "group_id": group_id,
        "transaction_id": transaction_id,
        "dedupe_key": f"group_deposit:{transaction_id}",
        "actor_id": str(owner.id),
    }

    asyncio.run(
        push_module.notify_all_group_members(
            group_id=group_id,
            sender_id=str(owner.id),
            title="Member just deposited",
            body="A deposit was made in Deposit Group.",
            data=data,
            include_sender_in_inbox=True,
        )
    )

    saved = session.exec(
        select(Notification).where(
            Notification.group_id == group_id,
            Notification.source_id == transaction_id,
        )
    ).all()
    assert {item.recipient_user_id for item in saved} == {
        owner.id,
        actor.id,
        other_user.id,
    }
