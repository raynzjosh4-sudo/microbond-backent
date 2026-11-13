from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Numeric, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RotatingReserveEntry(SQLModel, table=True):
    __tablename__ = "rotating_reserve_entry"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    cycle_id: UUID = Field(foreign_key="rotating_cycle.id", index=True)
    amount: Decimal = Field(sa_column=Column(Numeric, nullable=False))
    currency_code: str = Field(default="UGX")
    reason: str = Field(default="CYCLE_RESERVE", sa_type=Text)
    status: str = Field(default="HELD", index=True, sa_type=Text)
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    released_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
