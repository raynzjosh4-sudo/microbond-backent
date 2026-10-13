from typing import Optional
from sqlmodel import SQLModel, Field
import uuid
from sqlalchemy import Column, BigInteger
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class BillSplitMemberShare(SQLModel, table=True):
    """
    Individual member ledger and payment status for a BILL_SPLIT group.
    """
    __tablename__ = "billsplitmembershare"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)

    assigned_amount: int = Field(default=0, sa_column=Column(BigInteger), description="Portion owed by this member")
    amount_paid: int = Field(default=0, sa_column=Column(BigInteger), description="Amount paid toward the share so far")
    tip_paid: int = Field(default=0, sa_column=Column(BigInteger), description="Tip contributed by this member")
    is_settled: bool = Field(default=False, description="True once amount_paid >= assigned_amount")
    paid_at: Optional[int] = Field(default=None, sa_column=Column(BigInteger))
    payment_reference: Optional[str] = Field(default=None)

    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
