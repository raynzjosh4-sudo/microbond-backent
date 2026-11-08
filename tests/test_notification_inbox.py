import uuid

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
    client, _, _, _, other_user, notification = notification_context
    client.app.dependency_overrides[get_current_user] = lambda: other_user

    response = client.get(f"/api/v1/users/me/notifications/{notification.id}")
    assert response.status_code == 404

    response = client.post(
        f"/api/v1/users/me/notifications/{notification.id}/replies",
        json={"body": "Unauthorized reply"},
    )
    assert response.status_code == 404


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
