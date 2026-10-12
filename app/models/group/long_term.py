from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
from datetime import datetime, timezone
import uuid

def utc_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)

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
    created_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))


# ---------------------------------------------------------------------------
# FUNDRAISER GROUP — Two separate tables
# ---------------------------------------------------------------------------

class FundraiserCampaignConfig(SQLModel, table=True):
    """
    Set ONCE at group creation. All fields are LOCKED after creation.
    Protects donors — they know where money goes before they donate.
    """
    __tablename__ = "fundraisercampaignconfig"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)

    # 1. Campaign Target & Timeline (locked)
    target_amount: int = Field(default=0, sa_column=Column(BigInteger),
                               description="Total to raise. 0 = open-ended, no fixed goal.")
    campaign_deadline: Optional[int] = Field(default=None, sa_column=Column(BigInteger, nullable=True),
                                             description="When donations stop (epoch ms). Null = no deadline.")

    # 2. Where the Money Goes (locked)
    payout_destination_type: str = Field(default="NOMINATED_ACCOUNT",
                                         description="NOMINATED_ACCOUNT or SPLIT_EQUALLY")
    nominated_account_id: Optional[str] = Field(default=None,
                                                 description="Verified bank/mobile money account ID.")

    # 3. How the Money is Released (locked)
    payout_trigger_mode: str = Field(default="MANUAL",
                                     description="MANUAL (admin releases) or AUTO_ON_DEADLINE.")
    require_multi_signoff: bool = Field(default=False,
                                        description="Multiple signers must approve before money moves.")
    signoff_count_required: int = Field(default=1,
                                        description="Number of signers needed (only when multi-signoff is on).")

    created_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))


class FundraiserLiveStats(SQLModel, table=True):
    """
    Admin-editable settings + live campaign counters.
    These can be updated any time via the settings endpoint.
    """
    __tablename__ = "fundraiserlivestats"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)

    # Admin-editable settings
    allow_overfunding: bool = Field(default=True,
                                    description="Allow donations even after target_amount is hit.")
    stop_on_target_reached: bool = Field(default=False,
                                         description="Auto-close campaign the moment target is reached.")
    minimum_donation_amount: int = Field(default=500, sa_column=Column(BigInteger),
                                         description="Smallest donation accepted (e.g. 500 UGX).")

    # Campaign state (system-managed)
    is_active: bool = Field(default=True,
                            description="Is the campaign currently open for donations?")
    is_paid_out: bool = Field(default=False,
                              description="Has the money been sent out?")

    # Live counters (system-updated on each deposit)
    total_raised: int = Field(default=0, sa_column=Column(BigInteger),
                              description="Running total of all donations received.")
    donor_count: int = Field(default=0,
                             description="Number of unique people who have donated.")

    updated_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))


# ---------------------------------------------------------------------------
# SHARED WALLET GROUP — Two separate tables
# ---------------------------------------------------------------------------

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

    created_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))


class SharedWalletOperationalSettings(SQLModel, table=True):
    """
    Mutable spending limits, velocity limits, and live wallet balances.
    Managed via group settings.
    """
    __tablename__ = "sharedwalletoperationalsettings"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)

    # Operational Spending Limits
    minimum_balance_floor: int = Field(default=0, sa_column=Column(BigInteger), description="Reserve floor below which balance cannot drop")
    target_budget_limit: Optional[int] = Field(default=None, sa_column=Column(BigInteger, nullable=True), description="Max wallet cap")
    auto_approve_threshold: int = Field(default=0, sa_column=Column(BigInteger), description="Max amount disburseable without voting")
    approval_timeout_hours: int = Field(default=24, description="Voting window hours before spend request cancels")
    timelock_duration_hours: int = Field(default=0, description="Holding delay hours after approval before dispatch")

    # Velocity Controls
    daily_spending_cap: Optional[int] = Field(default=None, sa_column=Column(BigInteger, nullable=True), description="Max 24h spend cap")
    per_transaction_cap: Optional[int] = Field(default=None, sa_column=Column(BigInteger, nullable=True), description="Max single spend cap")
    allowed_disbursement_types: str = Field(
        default='["MEMBER_ACCOUNTS", "EXTERNAL_PAYEES"]',
        description="JSON array of allowed recipient types"
    )

    # Live Wallet State
    current_balance: int = Field(default=0, sa_column=Column(BigInteger))
    total_deposited: int = Field(default=0, sa_column=Column(BigInteger))
    total_spent: int = Field(default=0, sa_column=Column(BigInteger))
    is_active: bool = Field(default=True)

    updated_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))

