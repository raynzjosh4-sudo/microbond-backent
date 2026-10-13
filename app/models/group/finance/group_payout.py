from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class GroupPayout(SQLModel, table=True):
    """Tracks when a user receives the pooled money from a group."""
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    cycle_number: int = Field(default=1, index=True)
    
    amount_expected: int = Field(sa_column=Column(BigInteger))
    amount_received: int = Field(default=0, sa_column=Column(BigInteger))
    
    # Status: PENDING, PROCESSING, COMPLETED, FAILED, ON_HOLD
    status: str = Field(default="PENDING", index=True)
    hold_reason: Optional[str] = Field(default=None)
    
    payout_date: int = Field(sa_column=Column(BigInteger)) # Epoch ms
    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
