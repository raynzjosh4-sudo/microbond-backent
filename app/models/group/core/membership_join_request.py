from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, Text, text
from sqlmodel import Field, SQLModel
from app.models.user.invite import Invite


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MembershipJoinRequest(SQLModel, table=True):
    __tablename__ = "membership_join_request"
    __table_args__ = (
        Index(
            "uq_open_membership_join_request",
            "group_id",
            "user_id",
            unique=True,
            postgresql_where=text(
                "public_status NOT IN ('APPROVED', 'REJECTED', 'CANCELLED', 'EXPIRED')"
            ),
            sqlite_where=text(
                "public_status NOT IN ('APPROVED', 'REJECTED', 'CANCELLED', 'EXPIRED')"
            ),
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    invite_id: Optional[int] = Field(
        default=None,
        foreign_key=f"{Invite.__tablename__}.id",
        index=True,
    )
    user_id: UUID = Field(foreign_key="user.id", index=True)
    public_status: str = Field(default="DRAFT", index=True)
    guarantor_status: str = Field(default="NOT_REQUIRED")
    voting_status: str = Field(default="NOT_REQUIRED")
    admin_status: str = Field(default="NOT_REQUIRED")
    requires_guarantor: bool = Field(default=False)
    required_guarantors: int = Field(default=0, ge=0)
    requires_admin_approval: bool = Field(default=False)
    required_votes: int = Field(default=0, ge=0)
    approved_votes: int = Field(default=0, ge=0)
    rejection_reason: Optional[str] = Field(default=None, sa_type=Text)
    phone_verified_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
    )
    kyc_submitted_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
    )
    submitted_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
    )
    approved_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
    )
    rejected_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
    )
    cancelled_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_type=DateTime(timezone=True),
    )
