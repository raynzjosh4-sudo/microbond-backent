from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class AssociationDuesExemption(SQLModel, table=True):
    """
    Manages temporary or permanent dues exemptions for association members
    (e.g. students, hardship, elders, honorary members).
    """
    __tablename__ = "associationduesexemption"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)

    exemption_type: str = Field(default="TEMPORARY", description="TEMPORARY or PERMANENT")
    reason: str = Field(default="HARDSHIP", description="HARDSHIP, STUDENT, ELDER, HONORARY, SICKNESS, or OTHER")
    notes: Optional[str] = Field(default=None, description="Admin notes or justifications for exemption")
    discount_percentage: int = Field(default=100, description="Percentage of dues waived (100 = full exemption)")

    start_date: int = Field(sa_column=Column(BigInteger), description="Epoch ms when exemption starts")
    end_date: Optional[int] = Field(default=None, sa_column=Column(BigInteger), description="Epoch ms when exemption ends (None for PERMANENT)")
    is_active: bool = Field(default=True)
    approved_by: Optional[uuid.UUID] = Field(default=None, foreign_key="user.id")

    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
    updated_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
