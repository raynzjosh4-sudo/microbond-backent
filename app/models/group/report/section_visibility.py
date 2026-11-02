from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, func
from sqlmodel import Field, SQLModel


class GroupReportSectionVisibility(SQLModel, table=True):
    __tablename__ = "groupreportsectionvisibility"

    group_id: str = Field(
        primary_key=True,
        foreign_key="group.group_id",
        ondelete="CASCADE",
    )
    section_key: str = Field(sa_column=Column(String, primary_key=True))
    visible_to_members: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False, server_default="false"),
    )
    updated_by: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="user.id",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )