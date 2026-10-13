from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class MemberObligation(SQLModel, table=True):
    """Tracks every contribution a user is supposed to make to a group cycle."""
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    cycle_number: int = Field(default=1, index=True)
    
    amount_due: int = Field(sa_column=Column(BigInteger))
    amount_paid: int = Field(default=0, sa_column=Column(BigInteger))
    due_date: int = Field(sa_column=Column(BigInteger)) # Epoch ms
    
    # Status: PENDING, PAID, LATE, DEFAULTED
    status: str = Field(default="PENDING", index=True)
    
    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
    updated_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
