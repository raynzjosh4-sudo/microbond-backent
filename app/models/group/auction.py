from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
from sqlalchemy import Column, BigInteger
import uuid

def utc_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)

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
    
    created_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))
    updated_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))

class AuctionBid(SQLModel, table=True):
    """
    Represents an individual bid placed by a user in a GroupAuction.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    auction_id: str = Field(foreign_key="groupauction.auction_id", index=True)
    user_id: str = Field(index=True) # UUID string of bidder
    
    # The amount the user is willing to discount their payout (or pay upfront)
    bid_amount: float = Field(index=True)
    
    # ACTIVE (current highest), OUTBID (someone bid higher), CANCELLED
    status: str = Field(default="ACTIVE", index=True)
    
    created_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))
