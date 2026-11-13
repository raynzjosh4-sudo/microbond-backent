from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RotatingTurnSwap(SQLModel, table=True):
    __tablename__ = "rotating_turn_swap"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    requester_user_id: UUID = Field(foreign_key="user.id", index=True)
    target_user_id: UUID = Field(foreign_key="user.id", index=True)
    requester_cycle_number: int
    target_cycle_number: int
    status: str = Field(default="PENDING", index=True, sa_type=Text)
    approved_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    applied_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
