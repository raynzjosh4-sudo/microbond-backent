from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class LedgerEntry(SQLModel, table=True):
    """
    Immutable, double-entry accounting ledger.
    Never use += or -= on balances. Insert a LedgerEntry instead.
    Wallets are strictly a derived sum of these entries.
    """
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    
    # Financial Linkages (What triggered this money movement?)
    user_id: Optional[uuid.UUID] = Field(default=None, foreign_key="user.id", index=True)
    obligation_id: Optional[int] = Field(default=None, foreign_key="memberobligation.id", index=True)
    payout_id: Optional[int] = Field(default=None, foreign_key="grouppayout.id", index=True)
    penalty_id: Optional[int] = Field(default=None, foreign_key="grouppenalty.id", index=True)
    
    # Double Entry Accounts (Where did it come from, where did it go?)
    source_account: str = Field(index=True, description="e.g. MTN_MOMO, EXTERNAL_BANK, GROUP_POOLED, GROUP_RESERVE")
    destination_account: str = Field(index=True, description="e.g. GROUP_POOLED, USER_MOMO, GROUP_RESERVE")
    
    # Money (Stored as raw integer representing the smallest unit to prevent float drift)
    amount: int = Field(default=0, sa_column=Column(BigInteger))
    currency: str = Field(default="UGX")
    
    # Traceability
    transaction_type: str = Field(index=True, description="DEPOSIT, PAYOUT, PENALTY_FEE, INTERNAL_TRANSFER")
    external_reference_id: Optional[str] = Field(default=None, unique=True, index=True, description="Network TXN ID from MTN/Airtel")
    status: str = Field(default="PENDING", index=True, description="PENDING, SETTLED, FAILED, REVERSED")
    
    # Audit
    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
    settled_at: Optional[int] = Field(default=None, sa_column=Column(BigInteger))
