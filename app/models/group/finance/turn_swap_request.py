from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class TurnSwapRequest(SQLModel, table=True):
    """Tracks a request between two members to swap their payout cycles."""
    id: Optional[int] = Field(default=None, primary_key=True)
    swap_request_id: str = Field(default_factory=lambda: str(uuid.uuid4()), unique=True, index=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    
    requester_user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    target_user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    
    requester_cycle_number: int
    target_cycle_number: int
    
    # Status: PENDING, ACCEPTED, REJECTED, CANCELLED
    status: str = Field(default="PENDING", index=True)
    
    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
    updated_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
