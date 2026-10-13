from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class WelfareFundConfig(SQLModel, table=True):
    """
    Set ONCE at group creation. Defines the core rules of the safety net.
    These form the agreement all members accept when joining.
    """
    __tablename__ = "welfarefundconfig"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)

    # 1. Premium & Collection Schedule
    contribution_amount: int = Field(sa_column=Column(BigInteger), description="Mandatory premium per member per cycle")
    collection_frequency_days: int = Field(default=30, description="7=Weekly, 30=Monthly")
    waiting_period_days: int = Field(default=30, description="Days a new member waits before becoming eligible to claim")

    # 2. Claim Caps
    max_claim_amount_per_incident: int = Field(sa_column=Column(BigInteger), description="Max amount per single emergency claim")
    annual_claim_limit_per_member: int = Field(sa_column=Column(BigInteger), description="Max total claims one member receives per year")
    payout_destination_type: str = Field(default="MEMBER_ACCOUNT", description="MEMBER_ACCOUNT or EXTERNAL_SERVICE")

    # 3. Evidence & Approval Rules
    requires_documentary_evidence: bool = Field(default=True, description="Member must upload proof before claim is submitted")
    claim_approval_policy: str = Field(default="MAJORITY_VOTE", description="ADMIN_ONLY, WELFARE_COMMITTEE, MAJORITY_VOTE")

    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
