from typing import Optional, Any
from sqlmodel import SQLModel, Field, JSON
import uuid
from sqlalchemy import Column
from datetime import datetime, timezone

def utc_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)

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
    total_balance: int = Field(default=0) # Storing as integer/long
    
    # We remove the heavy JSON columns. Settings and Purpose data 
    # will be stored in separate dedicated tables (e.g. GroupSettings) 
    # linked by group_id so the main Group table stays fast and lightweight!
    
    # Membership
    member_count: int = Field(default=0)
    max_members: Optional[int] = Field(default=None)
    created_by_user_id: uuid.UUID = Field(foreign_key="user.id")
    invite_code: Optional[str] = Field(default=None, index=True, unique=True)
    
    # Shared content stats
    shared_media_count: int = Field(default=0)
    shared_ledger_entry_count: int = Field(default=0)
    
    # Audit
    created_at: int = Field(default_factory=utc_now)
    updated_at: int = Field(default_factory=utc_now)

class GroupMembership(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    membership_id: str = Field(unique=True, index=True) # UUID string
    
    group_id: str = Field(foreign_key="group.group_id", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    
    # Role & standing
    role: str = Field(default="MEMBER") # ADMIN, MEMBER, etc.
    title: Optional[str] = Field(default=None) # e.g. Treasurer
    status: str = Field(default="ACTIVE")
    group_trust_score: Optional[int] = Field(default=None)
    
    # Money in
    total_contributed: int = Field(default=0)
    
    # Private settings stored as JSON
    private_settings: Optional[dict[str, Any]] = Field(default_factory=dict, sa_column=Column(JSON))
    
    # Chat state
    is_favorite: bool = Field(default=False)
    unread_count: int = Field(default=0)
    
    # Lifecycle
    invited_by_user_id: Optional[uuid.UUID] = Field(default=None, foreign_key="user.id")
    joined_at: int = Field(default_factory=utc_now)
    left_at: Optional[int] = Field(default=None)

class MemberObligation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    obligation_id: str = Field(unique=True, index=True)
    
    group_id: str = Field(foreign_key="group.group_id", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    cycle_id: Optional[str] = Field(default=None, index=True)
    
    required_amount: int
    paid_amount: int = Field(default=0)
    due_date: int
    
    source: str = Field(description="ObligationSource enum")
    status: str = Field(default="DUE") # DUE, PAID, OVERDUE, WAIVED
    
    waived_by_user_id: Optional[uuid.UUID] = Field(default=None, foreign_key="user.id")
    created_at: int = Field(default_factory=utc_now)
