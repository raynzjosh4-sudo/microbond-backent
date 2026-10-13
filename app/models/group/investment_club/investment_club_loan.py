from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class InvestmentClubLoan(SQLModel, table=True):
    """
    Tracks internal credit facility loans taken by members against their equity stake.
    """
    __tablename__ = "investmentclubloan"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)

    principal_amount: int = Field(sa_column=Column(BigInteger), description="Loan capital requested in smallest currency unit")
    interest_rate_pct: float = Field(default=10.0, description="Interest rate agreed at approval")
    total_due_amount: int = Field(sa_column=Column(BigInteger), description="Principal + interest due")
    amount_repaid: int = Field(default=0, sa_column=Column(BigInteger), description="Total amount repaid to date")
    early_discount_applied: int = Field(default=0, sa_column=Column(BigInteger))

    status: str = Field(default="PENDING", description="PENDING, APPROVED, DISBURSED, REPAID, DEFAULTED, REJECTED")
    guarantors_count: int = Field(default=0)
    due_date: int = Field(sa_column=Column(BigInteger), description="Repayment deadline (epoch ms)")
    disbursed_at: Optional[int] = Field(default=None, sa_column=Column(BigInteger))
    settled_at: Optional[int] = Field(default=None, sa_column=Column(BigInteger))

    approved_by: Optional[uuid.UUID] = Field(default=None, foreign_key="user.id")
    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
    updated_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
