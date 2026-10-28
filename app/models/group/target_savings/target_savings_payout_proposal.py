from typing import Optional
import uuid

from sqlalchemy import BigInteger, Column
from sqlmodel import Field, SQLModel

from app.utils.time.now_epoch_ms import now_epoch_ms


class TargetSavingsPayoutProposal(SQLModel, table=True):
    __tablename__ = "targetsavingspayoutproposal"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    created_by_user_id: uuid.UUID = Field(foreign_key="user.id")
    provider_name: str
    account_type: str
    account_number: str
    account_name: str
    status: str = Field(default="PENDING")
    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))


class TargetSavingsPayoutApproval(SQLModel, table=True):
    __tablename__ = "targetsavingspayoutapproval"

    proposal_id: uuid.UUID = Field(
        foreign_key="targetsavingspayoutproposal.id",
        primary_key=True,
    )
    user_id: uuid.UUID = Field(foreign_key="user.id", primary_key=True)
    approved: bool
    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
