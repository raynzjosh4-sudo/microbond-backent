from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

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
    
    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
