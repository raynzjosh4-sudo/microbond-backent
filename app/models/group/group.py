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
    
    # Group Health & Discovery
    health_grade: str = Field(default="A+", description="A+, A, B, C, D")
    on_time_repayment_rate_pct: float = Field(default=100.0)
    active_default_rate_pct: float = Field(default=0.0)
    
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
    is_signer: bool = Field(default=False, description="Whether this member is on the multi-sig signer roster")
    auto_approve_small_requests: bool = Field(default=False)
    auto_approve_max_amount: Optional[float] = Field(default=None)
    
    # Rotating Settings
    payout_position: Optional[int] = Field(default=None, description="The assigned turn order in a rotating group (1, 2, 3...)")
    
    # Money in
    total_contributed: int = Field(default=0)
    
    # Personal Settings
    auto_pay_my_turn: bool = Field(default=True)
    proxy_contributor_id: Optional[uuid.UUID] = Field(default=None, foreign_key="user.id")
    payout_destination_id: Optional[str] = Field(default=None)
    payment_method_id: Optional[str] = Field(default=None)
    mute_notifications: bool = Field(default=False)
    custom_notification_tone: Optional[str] = Field(default="Default (Chime)")
    show_previews: bool = Field(default=True)
    include_chat_in_export: bool = Field(default=False)
    
    # Chat state
    is_favorite: bool = Field(default=False)
    is_chat_locked: bool = Field(default=False)
    unread_count: int = Field(default=0)
    
    # Lifecycle
    invited_by_user_id: Optional[uuid.UUID] = Field(default=None, foreign_key="user.id")
    joined_at: int = Field(default_factory=utc_now)
    left_at: Optional[int] = Field(default=None)
