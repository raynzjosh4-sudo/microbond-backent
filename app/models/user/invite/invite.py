from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlalchemy import DateTime, Text
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
    inviter_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    invitee_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    invite_token_hash: Optional[str] = Field(default=None, sa_type=Text)
    expires_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    max_uses: int = Field(default=1, gt=0)
    uses_count: int = Field(default=0, ge=0)
    accepted_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    declined_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    revoked_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(
        default_factory=now_utc_datetime,
        sa_type=DateTime(timezone=True),
    )
    group_public_id: Optional[str] = Field(default=None, foreign_key="group.group_id")
