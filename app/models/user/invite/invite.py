from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional
from app.utils.time.now_utc_datetime import now_utc_datetime

def utc_now():
    return now_utc_datetime()

class Invite(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    inviter_phone: str = Field(index=True)
    invitee_phone: str = Field(index=True)
    status: str = Field(default="pending")
    group_id: Optional[int] = Field(default=None, foreign_key="group.id")
    created_at: datetime = Field(default_factory=now_utc_datetime)
