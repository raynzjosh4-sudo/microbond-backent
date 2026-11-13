from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Index, JSON, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PaymentWebhookEvent(SQLModel, table=True):
    __tablename__ = "payment_webhook_event"
    __table_args__ = (
        Index(
            "uq_payment_webhook_provider_event",
            "provider_name",
            "provider_event_id",
            unique=True,
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    provider_name: str = Field(index=True, sa_type=Text)
    provider_event_id: str = Field(index=True, sa_type=Text)
    event_type: str = Field(sa_type=Text)
    payload_hash: str = Field(sa_type=Text)
    payload: Any = Field(sa_column=Column(JSON, nullable=False))
    status: str = Field(default="RECEIVED", index=True, sa_type=Text)
    received_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    processed_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    failure_reason: Optional[str] = Field(default=None, sa_type=Text)
