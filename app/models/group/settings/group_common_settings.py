from typing import Optional

from sqlalchemy import BigInteger, Column
from sqlmodel import Field, SQLModel

from app.utils.time.now_epoch_ms import now_epoch_ms


class GroupCommonSettings(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)

    allow_partial_payments: bool = Field(default=False)
    minimum_partial_payment_amount: Optional[float] = Field(default=None, gt=0)
    minimum_kyc_tier: int = Field(default=1, ge=0, le=3)
    group_start_time: Optional[int] = Field(default=None, sa_column=Column(BigInteger))
    require_guarantor: bool = Field(default=False)
    maximum_member_capacity: Optional[int] = Field(default=None)
    collection_frequency_days: Optional[int] = Field(default=None)
    grace_period_hours: int = Field(default=24)
    late_payment_policy: str = Field(default="STRIKE_AND_KEEP")
    payment_approval_threshold: Optional[int] = Field(
        default=None,
        sa_column=Column(BigInteger),
        description="Payment amount in UGX above which approval is required",
    )
    allow_advance_payments: bool = Field(default=True)

    updated_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
