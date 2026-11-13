from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Index, Numeric, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RotatingCycle(SQLModel, table=True):
    __tablename__ = "rotating_cycle"
    __table_args__ = (
        Index(
            "uq_rotating_cycle_group_number",
            "group_id",
            "cycle_number",
            unique=True,
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    cycle_number: int
    starts_at: datetime = Field(sa_type=DateTime(timezone=True))
    ends_at: datetime = Field(sa_type=DateTime(timezone=True))
    collection_start_time: time
    collection_end_time: time
    timezone_name: str = Field(default="Africa/Kampala", sa_type=Text)
    expected_pool_amount: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric, nullable=False))
    actual_collected_amount: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric, nullable=False))
    reserve_percentage: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric, nullable=False))
    reserve_amount: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric, nullable=False))
    available_payout_amount: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric, nullable=False))
    collection_rate_percentage: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric, nullable=False))
    status: str = Field(default="PLANNED", index=True, sa_type=Text)
    payout_readiness_status: str = Field(default="COLLECTING", sa_type=Text)
    closed_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    completed_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
