from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

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

    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
