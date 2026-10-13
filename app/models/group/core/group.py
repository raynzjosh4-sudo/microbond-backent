from typing import Optional
from sqlmodel import SQLModel, Field
import uuid
from sqlalchemy import Column, BigInteger
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class Group(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: str = Field(unique=True, index=True) # UUID string
    
    name: str
    description: str = Field(default="")
    group_image_url: str
    avatar_color: str = Field(default="Gray")
    
    # Classification
    type: str = Field(description="SavingsGroupType: MERRY_GO_ROUND, GOAL_SAVINGS, etc.")
    payment_mode: str = Field(description="OBLIGATION, VOLUNTARY, MIXED")
    savings_term: str = Field(default="LONG_TERM")
    visibility: str = Field(default="PRIVATE")
    status: str = Field(default="ACTIVE")
    
    # Financials & Timing
    currency: str = Field(default="UGX")
    total_balance: int = Field(default=0, sa_column=Column(BigInteger)) # Storing as BigInteger
    
    # Membership
    member_count: int = Field(default=0)
    max_members: Optional[int] = Field(default=None)
    created_by_user_id: uuid.UUID = Field(foreign_key="user.id")
    invite_code: Optional[str] = Field(default=None, index=True, unique=True)
    
    # Shared content stats
    shared_media_count: int = Field(default=0)
    shared_ledger_entry_count: int = Field(default=0)
    
    # Audit
    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
    updated_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
