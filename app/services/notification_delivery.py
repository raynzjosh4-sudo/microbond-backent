import logging
from typing import Any, Dict, Optional
import uuid

from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError

from app.core.database import engine
from app.models.user.notification import Notification
from app.models.user.user import User

logger = logging.getLogger(__name__)

_SOURCE_ID_KEYS = (
    "message_id",
    "transaction_id",
    "payment_id",
    "deposit_id",
    "payout_id",
    "event_id",
    "reference_id",
    "reply_id",
)


def _uuid_or_none(value: Optional[str]) -> Optional[uuid.UUID]:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        return None


def _notification_values(
    recipient_id: uuid.UUID,
    title: str,
    body: str,
    data: Dict[str, Any],
) -> Notification:
    event_type = str(data.get("type") or data.get("event_type") or "general")[:100]
    source_id = next(
        (str(data[key]) for key in _SOURCE_ID_KEYS if data.get(key) is not None),
        None,
    )
    source_type = data.get("source_type")
    if not source_type and source_id:
        source_type = (
            "group_chat_message" if event_type == "chat_message" else event_type
        )

    actor_user_id = _uuid_or_none(data.get("actor_id"))
    category = str(
        data.get("category")
        or (
            "messages"
            if event_type == "chat_message"
            else "transactions"
            if any(word in event_type.lower() for word in ("payment", "deposit", "payout", "transaction"))
            else "activity"
        )[:50]
    )
    dedupe_key = (
        f"{event_type}:{source_type or ''}:{source_id}" if source_id else None
    )
    payload = {str(key): str(value) for key, value in data.items() if value is not None}
    return Notification(
        recipient_user_id=recipient_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        category=category,
        title=title[:200],
        preview=body[:500],
        body=body,
        source_type=str(source_type)[:100] if source_type else None,
        source_id=source_id[:200] if source_id else None,
        payload=payload,
        can_reply=(
            event_type == "chat_message"
            and actor_user_id is not None
            and actor_user_id != recipient_id
            and data.get("can_reply") == "true"
        ),
        dedupe_key=dedupe_key[:500] if dedupe_key else None,
    )


def create_notifications_for_users(
    recipient_ids: list[uuid.UUID],
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
) -> None:
    """Persist notifications for recipients whether or not they have push tokens."""
    data = data or {}
    if not recipient_ids:
        return

    with Session(engine) as session:
        notifications = [
            _notification_values(recipient_id, title, body, data)
            for recipient_id in recipient_ids
        ]
        dedupe_keys = [item.dedupe_key for item in notifications if item.dedupe_key]
        if dedupe_keys:
            existing = session.exec(
                select(Notification.recipient_user_id, Notification.dedupe_key).where(
                    Notification.recipient_user_id.in_(recipient_ids),
                    Notification.dedupe_key.in_(dedupe_keys),
                )
            ).all()
            existing_keys = set(existing)
            notifications = [
                item
                for item in notifications
                if (item.recipient_user_id, item.dedupe_key) not in existing_keys
            ]
        if not notifications:
            return
        try:
            session.add_all(notifications)
            session.commit()
        except IntegrityError:
            session.rollback()
            logger.debug("Duplicate notification ignored for source %s", dedupe_keys)
        except Exception:
            session.rollback()
            logger.exception("Could not persist notifications in user inboxes")


def record_push_notification(
    token: str,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
) -> None:
    """Persist a snapshot of a push notification for each user owning the token."""
    with Session(engine) as session:
        recipients = session.exec(select(User).where(User.fcm_token == token)).all()
    if len(recipients) > 1:
        logger.warning("Multiple users share an FCM token; recording notifications for all")
    create_notifications_for_users(
        [recipient.id for recipient in recipients],
        title,
        body,
        data,
    )
