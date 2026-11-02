from datetime import date, datetime, timezone
from typing import Any, Dict, List
import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, JSON, String, func
from sqlmodel import Field, SQLModel


class GroupFinancialReport(SQLModel, table=True):
    __tablename__ = "groupfinancialreport"

    report_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        sa_column=Column(String, primary_key=True),
    )
    group_id: str = Field(foreign_key="group.group_id", index=True, ondelete="CASCADE")
    requester_user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    period_type: str = Field(default="WEEK")
    selected_date: date = Field(sa_column=Column(Date, nullable=False))
    start_date: date = Field(sa_column=Column(Date, nullable=False))
    end_date: date = Field(sa_column=Column(Date, nullable=False))
    included_sections: List[str] = Field(sa_column=Column(JSON, nullable=False))
    payload: Dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )