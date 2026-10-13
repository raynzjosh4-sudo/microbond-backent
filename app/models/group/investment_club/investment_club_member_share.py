from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class InvestmentClubMemberShare(SQLModel, table=True):
    """
    Tracks individual member equity shares and capital invested in the club.
    """
    __tablename__ = "investmentclubmembershare"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)

    shares_owned: int = Field(default=0, description="Number of shares held")
    total_invested: int = Field(default=0, sa_column=Column(BigInteger), description="Total amount paid for shares")
    last_dividend_received: int = Field(default=0, sa_column=Column(BigInteger))

    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
    updated_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
