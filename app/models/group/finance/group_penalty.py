from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class GroupPenalty(SQLModel, table=True):
    """Tracks specific late fees or infractions applied to a user."""
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    obligation_id: Optional[int] = Field(default=None, foreign_key="memberobligation.id")
    
    penalty_amount: int = Field(sa_column=Column(BigInteger))
    reason: str
    
    is_paid: bool = Field(default=False, index=True)
    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
