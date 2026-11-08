import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, update
from sqlmodel import Session, and_, or_, select

from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.models.user.notification import Notification, NotificationReply
from app.models.user.user import User
from app.utils.time.now_utc_datetime import now_utc_datetime

router = APIRouter(
    prefix="/api/v1/users/me/notifications",
    tags=["Notifications"],
)


class NotificationReplyRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    parent_reply_id: Optional[uuid.UUID] = None


def _notification_payload(notification: Notification) -> dict:
    return {
        "id": str(notification.id),
        "actor_user_id": str(notification.actor_user_id) if notification.actor_user_id else None,
        "event_type": notification.event_type,
        "category": notification.category,
        "title": notification.title,
        "preview": notification.preview,
        "body": notification.body,
        "source_type": notification.source_type,
        "source_id": notification.source_id,
        "payload": notification.payload,
        "can_reply": notification.can_reply,
        "created_at": notification.created_at,
        "read_at": notification.read_at,
    }


def _accessible_notification(
    notification_id: uuid.UUID,
    current_user: User,
    session: Session,
) -> Optional[Notification]:
    return session.exec(
        select(Notification).where(
            Notification.id == notification_id,
            or_(
                Notification.recipient_user_id == current_user.id,
                and_(
                    Notification.can_reply.is_(True),
                    Notification.actor_user_id == current_user.id,
                ),
            ),
        )
    ).first()


@router.get("")
def list_notifications(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    unread_only: bool = False,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    unread_count = session.exec(
        select(func.count())
        .select_from(Notification)
        .where(
            Notification.recipient_user_id == current_user.id,
            Notification.read_at.is_(None),
        )
    ).one()

    query = select(Notification).where(
        Notification.recipient_user_id == current_user.id
    )
    if unread_only:
        query = query.where(Notification.read_at.is_(None))

    notifications = session.exec(
        query.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [_notification_payload(item) for item in notifications],
        "limit": limit,
        "offset": offset,
        "unread_count": unread_count,
    }


@router.get("/{notification_id}")
def get_notification(
    notification_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    notification = _accessible_notification(notification_id, current_user, session)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found.")

    if (
        notification.recipient_user_id == current_user.id
        and notification.read_at is None
    ):
        notification.read_at = now_utc_datetime()
        session.add(notification)
        session.commit()
        session.refresh(notification)

    replies = session.exec(
        select(NotificationReply)
        .where(NotificationReply.notification_id == notification.id)
        .order_by(NotificationReply.created_at, NotificationReply.id)
    ).all()
    user_ids = {reply.sender_user_id for reply in replies}
    users = (
        session.exec(select(User).where(User.id.in_(user_ids))).all()
        if user_ids
        else []
    )
    user_names = {user.id: user.full_name for user in users}

    payload = _notification_payload(notification)
    payload["replies"] = [
        {
            "id": str(reply.id),
            "sender_user_id": str(reply.sender_user_id),
            "sender_name": user_names.get(reply.sender_user_id),
            "parent_reply_id": str(reply.parent_reply_id) if reply.parent_reply_id else None,
            "body": reply.body,
            "created_at": reply.created_at,
        }
        for reply in replies
    ]
    return payload


@router.patch("/{notification_id}/read")
def mark_notification_read(
    notification_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    notification = session.exec(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_user_id == current_user.id,
        )
    ).first()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found.")
    if notification.read_at is None:
        notification.read_at = now_utc_datetime()
        session.add(notification)
        session.commit()
    return {"status": "success", "read_at": notification.read_at}


@router.post("/read-all")
def mark_all_notifications_read(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    read_at = now_utc_datetime()
    result = session.exec(
        update(Notification)
        .where(
            Notification.recipient_user_id == current_user.id,
            Notification.read_at.is_(None),
        )
        .values(read_at=read_at)
    )
    session.commit()
    return {"status": "success", "updated_count": result.rowcount}


@router.post(
    "/{notification_id}/replies",
    status_code=status.HTTP_201_CREATED,
)
def reply_to_notification(
    notification_id: uuid.UUID,
    request: NotificationReplyRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    notification = _accessible_notification(notification_id, current_user, session)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found.")
    if not notification.can_reply:
        raise HTTPException(
            status_code=409,
            detail="Replies are not enabled for this notification.",
        )

    body = request.body.strip()
    if not body:
        raise HTTPException(status_code=422, detail="Reply body must not be empty.")

    if request.parent_reply_id:
        parent = session.exec(
            select(NotificationReply).where(
                NotificationReply.id == request.parent_reply_id,
                NotificationReply.notification_id == notification.id,
            )
        ).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Reply thread entry not found.")

    reply = NotificationReply(
        notification_id=notification.id,
        sender_user_id=current_user.id,
        parent_reply_id=request.parent_reply_id,
        body=body,
    )
    session.add(reply)
    session.commit()
    session.refresh(reply)

    reply_recipient_id = (
        notification.actor_user_id
        if notification.recipient_user_id == current_user.id
        else notification.recipient_user_id
    )
    if reply_recipient_id and reply_recipient_id != current_user.id:
        from app.services.notification_delivery import create_notifications_for_users

        create_notifications_for_users(
            [reply_recipient_id],
            "New reply to your notification",
            body,
            {
                "type": "notification_reply",
                "category": "messages",
                "source_type": "notification_reply",
                "reply_id": str(reply.id),
                "notification_id": str(notification.id),
                "actor_id": str(current_user.id),
            },
        )

    return {
        "id": str(reply.id),
        "notification_id": str(reply.notification_id),
        "sender_user_id": str(reply.sender_user_id),
        "parent_reply_id": str(reply.parent_reply_id) if reply.parent_reply_id else None,
        "body": reply.body,
        "created_at": reply.created_at,
    }
