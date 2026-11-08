import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import Column, DateTime, Index, JSON, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.utils.time.now_utc_datetime import now_utc_datetime


class Notification(SQLModel, table=True):
    __table_args__ = (
        Index("ix_notification_recipient_created", "recipient_user_id", "created_at"),
        Index("ix_notification_recipient_read", "recipient_user_id", "read_at"),
        Index("ix_notification_source", "source_type", "source_id"),
        UniqueConstraint(
            "recipient_user_id",
            "dedupe_key",
            name="uq_notification_recipient_dedupe",
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    recipient_user_id: uuid.UUID = Field(
        foreign_key="user.id",
        ondelete="CASCADE",
        nullable=False,
    )
    actor_user_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="user.id",
        ondelete="SET NULL",
    )
    event_type: str = Field(max_length=100)
    category: str = Field(max_length=50)
    title: str = Field(max_length=200)
    preview: Optional[str] = Field(default=None, max_length=500)
    body: str = Field(sa_column=Column(Text, nullable=False))
    source_type: Optional[str] = Field(default=None, max_length=100)
    source_id: Optional[str] = Field(default=None, max_length=200)
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    can_reply: bool = Field(default=False, nullable=False)
    dedupe_key: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(
        default_factory=now_utc_datetime,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    read_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )


class NotificationReply(SQLModel, table=True):
    __table_args__ = (
        Index("ix_notificationreply_notification_created", "notification_id", "created_at"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    notification_id: uuid.UUID = Field(
        foreign_key="notification.id",
        ondelete="CASCADE",
        nullable=False,
    )
    sender_user_id: uuid.UUID = Field(
        foreign_key="user.id",
        ondelete="CASCADE",
        nullable=False,
    )
    parent_reply_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="notificationreply.id",
        ondelete="CASCADE",
    )
    body: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(
        default_factory=now_utc_datetime,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
