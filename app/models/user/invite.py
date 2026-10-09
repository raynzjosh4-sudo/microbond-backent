from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
from typing import Optional

def utc_now():
    return datetime.now(timezone.utc)

class Invite(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    inviter_phone: str = Field(index=True)
    invitee_phone: str = Field(index=True)
    status: str = Field(default="pending")
    group_id: Optional[int] = Field(default=None, foreign_key="group.id")
    created_at: datetime = Field(default_factory=utc_now)
