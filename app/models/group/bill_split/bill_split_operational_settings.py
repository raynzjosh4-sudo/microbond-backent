from typing import Optional
from sqlmodel import SQLModel, Field
import uuid
from sqlalchemy import Column, BigInteger
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

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

    updated_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
