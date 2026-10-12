from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
from datetime import datetime, timezone
import uuid


def utc_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


# ---------------------------------------------------------------------------
# WELFARE FUND GROUP — Two separate tables
# ---------------------------------------------------------------------------

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

    created_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))


class WelfareFundOperationalSettings(SQLModel, table=True):
    """
    Admin-managed settings + live fund counters.
    Updated via group settings endpoint.
    """
    __tablename__ = "welfarefundoperationalsettings"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)

    # Admin-editable settings
    minimum_reserve_balance: int = Field(default=0, sa_column=Column(BigInteger), description="Claims paused if pool drops below this")
    approval_timeout_hours: int = Field(default=48, description="Hours for group to vote before claim expires")
    missed_payment_action: str = Field(default="SUSPEND_CLAIM_RIGHTS", description="SUSPEND_CLAIM_RIGHTS or RECORD_STRIKE")
    enable_late_fees: bool = Field(default=False)
    allow_annual_dividend_split: bool = Field(default=False, description="Allow year-end vote to return unused funds proportionally")

    # Live counters (system-updated)
    current_balance: int = Field(default=0, sa_column=Column(BigInteger))
    total_collected: int = Field(default=0, sa_column=Column(BigInteger))
    total_paid_out: int = Field(default=0, sa_column=Column(BigInteger))
    is_active: bool = Field(default=True)

    updated_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))


# ---------------------------------------------------------------------------
# EVENT COMMITTEE GROUP — Two separate tables
# ---------------------------------------------------------------------------

class EventCommitteeConfig(SQLModel, table=True):
    """
    Set ONCE at group creation. Defines the event facts and disbursement rules.
    """
    __tablename__ = "eventcommitteeconfig"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)

    # 1. Event Budget & Timeline
    event_target_budget: int = Field(default=0, sa_column=Column(BigInteger), description="Total estimated event cost")
    event_date: int = Field(sa_column=Column(BigInteger), description="When the event happens (epoch ms)")
    collection_deadline: int = Field(sa_column=Column(BigInteger), description="Last date funds must be deposited (epoch ms)")

    # 2. Vendor / Payout Rules
    payout_destination_type: str = Field(default="VERIFIED_VENDORS_ONLY", description="VERIFIED_VENDORS_ONLY or COMMITTEE_TREASURER")
    spending_signoff_policy: str = Field(default="CHAIRMAN_ONLY", description="CHAIRMAN_ONLY or COMMITTEE_CONSENSUS")
    excess_funds_action: str = Field(default="PROPORTIONAL_REFUND", description="GIFT_TO_BENEFICIARY, PROPORTIONAL_REFUND, ROLLOVER_TO_NEW_EVENT")
    require_invoice_upload: bool = Field(default=True, description="Admin must upload invoice photo before releasing funds")

    created_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))


class EventCommitteeOperationalSettings(SQLModel, table=True):
    """
    Admin-managed settings + live collection tracker.
    Updated via group settings endpoint.
    """
    __tablename__ = "eventcommitteeoperationalsettings"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)

    # Admin-editable settings
    allow_overfunding: bool = Field(default=False, description="Accept deposits past target budget")
    track_pledges: bool = Field(default=True, description="Track promised vs. actual deposits")
    minimum_contribution_amount: int = Field(default=0, sa_column=Column(BigInteger), description="Smallest accepted deposit")
    member_quota_amount: int = Field(default=0, sa_column=Column(BigInteger), description="Equal amount everyone must pay (0 = no quota)")
    allow_guest_deposits: bool = Field(default=False, description="Generate public link for non-member contributions")
    allow_partial_disbursements: bool = Field(default=False, description="Allow partial vendor payments before deadline")
    signoff_trustee_user_ids: str = Field(default="[]", description="JSON array of user IDs required to approve payments")

    # Live counters (system-updated)
    current_balance: int = Field(default=0, sa_column=Column(BigInteger))
    total_pledged: int = Field(default=0, sa_column=Column(BigInteger))
    total_disbursed: int = Field(default=0, sa_column=Column(BigInteger))
    is_active: bool = Field(default=True)

    updated_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))
