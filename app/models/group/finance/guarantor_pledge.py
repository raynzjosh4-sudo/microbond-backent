from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import BigInteger, Column, Text
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class GuarantorPledge(SQLModel, table=True):
    """Legal-style record of a member backing another member."""
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    guarantor_user_id: uuid.UUID = Field(foreign_key="user.id", index=True) # UUID
    borrower_user_id: uuid.UUID = Field(foreign_key="user.id", index=True) # UUID
    
    maximum_liability_amount: int = Field(sa_column=Column(BigInteger))
    
    # Status: ACTIVE (protecting), TRIGGERED (funds frozen/taken), RELEASED (safe)
    status: str = Field(default="ACTIVE", index=True)
    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
    pledge_token_hash: Optional[str] = Field(default=None, sa_type=Text)
