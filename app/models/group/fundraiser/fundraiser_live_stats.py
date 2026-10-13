from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

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

    updated_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
