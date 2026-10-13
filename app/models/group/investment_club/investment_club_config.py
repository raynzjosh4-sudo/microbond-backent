from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class InvestmentClubConfig(SQLModel, table=True):
    """
    Set ONCE at group creation. Constitutional equity & voting rules.
    """
    __tablename__ = "investmentclubconfig"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)

    share_unit_price: int = Field(sa_column=Column(BigInteger), description="Cost of one equity share in smallest currency unit")
    equity_calculation_mode: str = Field(default="PROPORTIONAL_TO_SHARES", description="PROPORTIONAL_TO_SHARES or FIXED_EQUAL")
    voting_power_logic: str = Field(default="PROPORTIONAL", description="PROPORTIONAL or ONE_MEMBER_ONE_VOTE")
    payout_destination_type: str = Field(default="VERIFIED_BROKERS_ONLY", description="VERIFIED_BROKERS_ONLY or REGISTERED_ASSET_ACCOUNT")
    dividend_distribution_rule: str = Field(default="AUTO_PUSH_PROPORTIONAL", description="AUTO_PUSH_PROPORTIONAL or REINVEST_IN_VAULT")
    lock_in_period_days: int = Field(default=180, description="Minimum days member capital is locked before withdrawal")
    liquidation_action: str = Field(default="LIQUIDATE_PROPORTIONAL", description="Action upon dissolution: LIQUIDATE_PROPORTIONAL")

    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
