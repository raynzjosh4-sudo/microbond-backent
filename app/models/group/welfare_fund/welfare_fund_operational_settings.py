from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

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

    updated_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
