from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

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

    updated_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
