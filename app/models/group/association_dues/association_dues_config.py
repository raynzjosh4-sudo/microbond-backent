from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class AssociationDuesConfig(SQLModel, table=True):
    """
    Set ONCE at group creation. Defines subscription dues rules & treasury routing.
    """
    __tablename__ = "associationduesconfig"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)

    dues_amount: int = Field(sa_column=Column(BigInteger), description="Mandatory recurring subscription fee")
    billing_cycle_days: int = Field(default=30, description="Cycle interval: 30=Monthly, 90=Quarterly, 365=Annually")
    billing_start_date: int = Field(sa_column=Column(BigInteger), description="When first cycle officially commences (epoch ms)")
    treasury_account_id: str = Field(description="UUID of verified Bank or MoMo account belonging to Association")
    enable_prorated_dues: bool = Field(default=True, description="Prorate dues for members joining mid-cycle")

    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
