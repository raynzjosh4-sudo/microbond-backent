from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
from datetime import datetime, timezone

def utc_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)

class GroupSettings(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)
    
    # AdvancedGroupPrivacySettings
    hide_balances: bool = Field(default=False)
    hide_member_contact: bool = Field(default=True)
    invite_only: bool = Field(default=True)
    
    # ApprovalProcessSettings & Quorum
    approval_strategy: str = Field(default="Majority Vote")
    quorum_percentage: str = Field(default="60%")
    
    # ArrearsPolicySettings
    arrears_policy: str = Field(default="Deduct from next payout")
    
    # LateFeeSettings
    enable_late_fees: bool = Field(default=True)
    late_fee_amount: str = Field(default="10,000 UGX")
    late_fee_frequency: str = Field(default="Per day")
    
    # GracePeriodSettings
    enable_grace_period: bool = Field(default=True)
    grace_period_duration: str = Field(default="24 Hours")
    
    # Trust & Roles
    minimum_trust_score: Optional[int] = Field(default=None)
    require_guarantors: bool = Field(default=True)
    guarantor_count: int = Field(default=2)
    
    # Payout Limits
    max_payout_active: bool = Field(default=True)
    max_payout_limit: str = Field(default="10,000,000 UGX")
    
    # Auditing
    is_audit_active: bool = Field(default=False)
    
    # Timelock / Escrow
    enable_escrow: bool = Field(default=True)
    escrow_release_time: str = Field(default="Upon unanimous approval")
    enable_timelock: bool = Field(default=True)
    timelock_duration: str = Field(default="24 Hours")
    
    updated_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))
