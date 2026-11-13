from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Index, Numeric, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RotatingDailyCollection(SQLModel, table=True):
    __tablename__ = "rotating_daily_collection"
    __table_args__ = (
        Index(
            "uq_rotating_collection_cycle_user_date",
            "cycle_id",
            "user_id",
            "collection_date",
            unique=True,
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    cycle_id: UUID = Field(foreign_key="rotating_cycle.id", index=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    collection_date: date = Field(index=True)
    window_start: datetime = Field(sa_type=DateTime(timezone=True))
    window_end: datetime = Field(sa_type=DateTime(timezone=True))
    amount_due: Decimal = Field(sa_column=Column(Numeric, nullable=False))
    amount_paid: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric, nullable=False))
    status: str = Field(default="PENDING", index=True, sa_type=Text)
    payment_reference: Optional[str] = Field(default=None, sa_type=Text)
    paid_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    late_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
