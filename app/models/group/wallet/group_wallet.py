from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class GroupWallet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)
    
    # The primary pool where member contributions for the current cycle go
    pooled_funds: int = Field(default=0, description="Virtual balance of member contributions", sa_column=Column(BigInteger))
    
    # The reserve/cut pool
    reserve_funds: int = Field(default=0, description="Virtual balance for admin cuts, late fees, or emergencies", sa_column=Column(BigInteger))
    
    # Total historical processed out of the group
    total_lifetime_payouts: int = Field(default=0, description="Total amount paid out to members over time", sa_column=Column(BigInteger))
    
    updated_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
