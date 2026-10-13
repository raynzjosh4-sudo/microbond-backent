from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class GroupAuction(SQLModel, table=True):
    """
    Represents a specific auction cycle where members bid for the payout.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    auction_id: str = Field(default_factory=lambda: str(uuid.uuid4()), unique=True, index=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    cycle_number: int = Field(index=True)
    
    # Timing
    start_time: int = Field(sa_column=Column(BigInteger)) # Epoch ms
    end_time: int = Field(sa_column=Column(BigInteger))   # Epoch ms (can be extended by popcorn bidding)
    
    # State: PENDING, ACTIVE, CLOSED, RESOLVED
    status: str = Field(default="PENDING", index=True)
    
    # The winning outcome
    winning_bid_id: Optional[int] = Field(default=None, foreign_key="auctionbid.id")
    winning_user_id: Optional[str] = Field(default=None) # UUID string of winner
    
    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
    updated_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
