from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class AssociationMemberDuesStanding(SQLModel, table=True):
    """
    Tracks individual member subscription cycles, payment status, and arrears.
    """
    __tablename__ = "associationmemberduesstanding"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)

    cycles_paid_ahead: int = Field(default=0, description="Number of future cycles prepaid")
    consecutive_missed_cycles: int = Field(default=0, description="Consecutive unpaid cycles")
    outstanding_arrears_balance: int = Field(default=0, sa_column=Column(BigInteger), description="Total unpaid dues and late fees")
    is_in_arrears: bool = Field(default=False)
    is_suspended: bool = Field(default=False)
    last_payment_date: Optional[int] = Field(default=None, sa_column=Column(BigInteger))
    next_due_date: int = Field(sa_column=Column(BigInteger))

    updated_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
