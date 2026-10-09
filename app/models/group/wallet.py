from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
from sqlalchemy import Column, BigInteger

def utc_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)

class GroupWallet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)
    
    # The primary pool where member contributions for the current cycle go
    pooled_funds: float = Field(default=0.0, description="Virtual balance of member contributions")
    
    # The reserve/cut pool
    reserve_funds: float = Field(default=0.0, description="Virtual balance for admin cuts, late fees, or emergencies")
    
    # Total historical processed out of the group
    total_lifetime_payouts: float = Field(default=0.0, description="Total amount paid out to members over time")
    
    updated_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))
