from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Index, Text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BackendJobExecution(SQLModel, table=True):
    __tablename__ = "backend_job_execution"
    __table_args__ = (
        Index(
            "uq_backend_job_idempotency",
            "job_type",
            "idempotency_key",
            unique=True,
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    job_type: str = Field(index=True, sa_type=Text)
    idempotency_key: str = Field(index=True, sa_type=Text)
    group_id: Optional[str] = Field(default=None, foreign_key="group.group_id", index=True)
    cycle_id: Optional[UUID] = Field(default=None, foreign_key="rotating_cycle.id", index=True)
    status: str = Field(default="PENDING", index=True, sa_type=Text)
    attempts: int = Field(default=0)
    available_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    locked_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    locked_by: Optional[str] = Field(default=None, sa_type=Text)
    last_error: Optional[str] = Field(default=None, sa_type=Text)
    created_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    completed_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
