from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class SharedWalletConfig(SQLModel, table=True):
    """
    Set ONCE at group creation. Fundamental rules agreed upon by members.
    """
    __tablename__ = "sharedwalletconfig"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)

    # 1. Replenishment Model
    replenishment_mode: str = Field(default="FLEXIBLE", description="FLEXIBLE or SCHEDULED_QUOTA")
    member_quota_amount: int = Field(default=0, sa_column=Column(BigInteger), description="Amount per member per cycle")
    collection_frequency_days: int = Field(default=0, description="0=Daily/Flexible, 7=Weekly, 30=Monthly")

    # 2. Spending Signoff Policy
    spending_signoff_policy: str = Field(
        default="ADMIN_ONLY",
        description="ADMIN_ONLY, ANY_MEMBER_WITH_APPROVAL, MAJORITY_VOTE, UNANIMOUS"
    )

    # 3. Exit & Dissolution Rules
    exit_payout_rule: str = Field(
        default="PROPORTIONAL_REMAINING",
        description="PROPORTIONAL_REMAINING, EQUAL_SPLIT, CONSENSUS_DISTRIBUTION"
    )

    # 4. Accounting & KYC
    track_individual_contributions: bool = Field(default=True)
    minimum_kyc_tier: int = Field(default=1)

    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
