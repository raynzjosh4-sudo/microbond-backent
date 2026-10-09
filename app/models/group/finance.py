from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
from sqlalchemy import Column, BigInteger
import uuid

def utc_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)

class MemberObligation(SQLModel, table=True):
    """Tracks every contribution a user is supposed to make to a group cycle."""
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    cycle_number: int = Field(default=1, index=True)
    
    amount_due: float
    amount_paid: float = Field(default=0.0)
    due_date: int = Field(sa_column=Column(BigInteger)) # Epoch ms
    
    # Status: PENDING, PAID, LATE, DEFAULTED
    status: str = Field(default="PENDING", index=True)
    
    created_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))
    updated_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))

class GroupPayout(SQLModel, table=True):
    """Tracks when a user receives the pooled money from a group."""
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    cycle_number: int = Field(default=1, index=True)
    
    amount_expected: float
    amount_received: float = Field(default=0.0)
    
    # Status: PENDING, PROCESSING, COMPLETED, FAILED, ON_HOLD
    status: str = Field(default="PENDING", index=True)
    hold_reason: Optional[str] = Field(default=None)
    
    payout_date: int = Field(sa_column=Column(BigInteger)) # Epoch ms
    created_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))

class GroupPenalty(SQLModel, table=True):
    """Tracks specific late fees or infractions applied to a user."""
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    obligation_id: Optional[int] = Field(default=None, foreign_key="memberobligation.id")
    
    penalty_amount: float
    reason: str
    
    is_paid: bool = Field(default=False, index=True)
    created_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))

class GuarantorPledge(SQLModel, table=True):
    """Legal-style record of a member backing another member."""
    id: Optional[int] = Field(default=None, primary_key=True)
    pledge_token: str = Field(default_factory=lambda: str(uuid.uuid4()), unique=True, index=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    guarantor_user_id: uuid.UUID = Field(foreign_key="user.id", index=True) # UUID
    borrower_user_id: uuid.UUID = Field(foreign_key="user.id", index=True) # UUID
    
    maximum_liability_amount: float
    
    # Status: ACTIVE (protecting), TRIGGERED (funds frozen/taken), RELEASED (safe)
    status: str = Field(default="ACTIVE", index=True)
    created_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))

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
    
    created_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))
    updated_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))
