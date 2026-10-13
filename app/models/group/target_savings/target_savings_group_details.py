from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class TargetSavingsGroupDetails(SQLModel, table=True):
    __tablename__ = "targetsavingsgroupdetails"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)
    
    # 1. Savings Goal & Schedule (Whole Numbers Only)
    target_amount: int = Field(default=0, sa_column=Column(BigInteger))
    target_date: int = Field(sa_column=Column(BigInteger))
    contribution_amount: int = Field(default=0, sa_column=Column(BigInteger))
    collection_frequency_days: int = Field(default=0)
    collection_time: Optional[int] = Field(default=None, sa_column=Column(BigInteger))
    
    # 2. Where the Money Goes at the End
    payout_destination_type: str = Field(default="PROPORTIONAL_RETURN")
    nominated_account_id: Optional[str] = Field(default=None)
    
    # 3. Group Agreement & Voting Rules
    require_consensus_at_end: bool = Field(default=False)
    allow_early_payout_by_vote: bool = Field(default=True)
    vote_approval_percentage: int = Field(default=100)
    
    # 4. Late Fees & Rules
    enable_late_fees: bool = Field(default=False)
    late_fee_amount: int = Field(default=0, sa_column=Column(BigInteger))
    grace_period_hours: int = Field(default=24)
    missed_payment_action: str = Field(default="RECORD_STRIKE")
    minimum_kyc_tier: int = Field(default=1)
    hide_leaderboard: bool = Field(default=False)
    
    # 5. Savings Status
    is_locked: bool = Field(default=True)
    is_ended: bool = Field(default=False)
    is_paid_out: bool = Field(default=False)
    total_saved_amount: int = Field(default=0, sa_column=Column(BigInteger))
    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
