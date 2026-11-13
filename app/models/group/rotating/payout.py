from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Index, Numeric, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RotatingPayout(SQLModel, table=True):
    __tablename__ = "rotating_payout"
    __table_args__ = (
        Index("uq_rotating_payout_cycle", "cycle_id", unique=True),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    cycle_id: UUID = Field(foreign_key="rotating_cycle.id", index=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    cycle_number: int
    gross_pool_amount: Decimal = Field(sa_column=Column(Numeric, nullable=False))
    reserve_amount: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric, nullable=False))
    net_payout_amount: Decimal = Field(sa_column=Column(Numeric, nullable=False))
    recipient_count: int
    amount_per_recipient: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric))
    status: str = Field(default="PENDING", index=True, sa_type=Text)
    hold_reason: Optional[str] = Field(default=None, sa_type=Text)
    approval_required: bool = Field(default=False)
    required_approval_count: int = Field(default=0)
    approved_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    approved_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    disbursed_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    failed_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))


class RotatingPayoutRecipient(SQLModel, table=True):
    __tablename__ = "rotating_payout_recipient"
    __table_args__ = (
        Index(
            "uq_rotating_recipient_position",
            "payout_id",
            "turn_position",
            unique=True,
        ),
        Index(
            "uq_rotating_recipient_user",
            "payout_id",
            "user_id",
            unique=True,
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    payout_id: UUID = Field(foreign_key="rotating_payout.id", index=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    turn_position: int
    amount: Decimal = Field(sa_column=Column(Numeric, nullable=False))
    payout_destination_id: Optional[str] = Field(
        default=None,
        foreign_key="userpayoutdestination.id",
    )
    status: str = Field(default="PENDING", index=True, sa_type=Text)
    external_reference_id: Optional[str] = Field(default=None, sa_type=Text)
    disbursed_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
