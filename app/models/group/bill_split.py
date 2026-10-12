from typing import Optional
from sqlmodel import SQLModel, Field
import uuid
from sqlalchemy import Column, BigInteger
from datetime import datetime, timezone

def utc_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)

# ==============================================================================
# BILL SPLIT GROUP — Core Configuration & Operational Settings
# ==============================================================================

class BillSplitConfig(SQLModel, table=True):
    """
    IMMUTABLE Group Creation Configuration for BILL_SPLIT groups.
    Defines the baseline terms of the split expense agreed upon at creation time.
    """
    __tablename__ = "billsplitconfig"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", unique=True, index=True)

    # Core Bill Terms
    total_bill_amount: int = Field(sa_column=Column(BigInteger), description="Total amount of the bill in smallest currency unit")
    split_mode: str = Field(default="EQUAL", description="EQUAL, EXACT, PERCENTAGE, BY_SHARES")
    settlement_deadline: Optional[int] = Field(default=None, sa_column=Column(BigInteger), description="Epoch ms by which all members must settle")
    bill_category: str = Field(default="GENERAL", description="GENERAL, DINING, TRAVEL, UTILITIES, RENT, ENTERTAINMENT")

    # Settlement Destination & Payee
    payout_destination_type: str = Field(default="ORGANIZER_WALLET", description="ORGANIZER_WALLET, MERCHANT_TILL, BILLER_DIRECT")
    payee_identifier: Optional[str] = Field(default=None, description="Merchant till number, phone number, or bill account number")
    payee_name: Optional[str] = Field(default=None, description="Display name of payee or vendor (e.g., 'Café Javas')")
    bill_receipt_url: Optional[str] = Field(default=None, description="URL to bill receipt or invoice photo")

    created_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))


class BillSplitOperationalSettings(SQLModel, table=True):
    """
    MUTABLE Operational Settings and Live Counters for BILL_SPLIT groups.
    Can be updated dynamically by group admins during the lifecycle.
    """
    __tablename__ = "billsplitoperationalsettings"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", unique=True, index=True)

    # Policy controls
    allow_tip_or_extra: bool = Field(default=True, description="Allow members to contribute tip or extra buffer")
    auto_close_on_settlement: bool = Field(default=True, description="Auto-mark settled once 100% of bill amount is collected")
    send_reminder_hours_before: int = Field(default=24, description="Hours before deadline to ping defaulters")

    # Late fee rules (synced with general settings)
    enable_late_fees: bool = Field(default=False)
    late_fee_amount: int = Field(default=0, sa_column=Column(BigInteger))
    grace_period_hours: int = Field(default=24)

    # Live Counters & State
    is_settled: bool = Field(default=False, description="True when the bill is fully paid or closed")
    total_collected: int = Field(default=0, sa_column=Column(BigInteger), description="Sum of member contributions towards bill")
    total_tip_collected: int = Field(default=0, sa_column=Column(BigInteger), description="Accumulated tip/extra contributions")
    settled_at: Optional[int] = Field(default=None, sa_column=Column(BigInteger))

    updated_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))


class BillSplitMemberShare(SQLModel, table=True):
    """
    Individual member ledger and payment status for a BILL_SPLIT group.
    """
    __tablename__ = "billsplitmembershare"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)

    assigned_amount: int = Field(default=0, sa_column=Column(BigInteger), description="Portion owed by this member")
    amount_paid: int = Field(default=0, sa_column=Column(BigInteger), description="Amount paid toward the share so far")
    tip_paid: int = Field(default=0, sa_column=Column(BigInteger), description="Tip contributed by this member")
    is_settled: bool = Field(default=False, description="True once amount_paid >= assigned_amount")
    paid_at: Optional[int] = Field(default=None, sa_column=Column(BigInteger))
    payment_reference: Optional[str] = Field(default=None)

    created_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))
