from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class SharedWalletOperationalSettings(SQLModel, table=True):
    """
    Mutable spending limits, velocity limits, and live wallet balances.
    Managed via group settings.
    """
    __tablename__ = "sharedwalletoperationalsettings"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)

    # Operational Spending Limits
    minimum_balance_floor: int = Field(default=0, sa_column=Column(BigInteger), description="Reserve floor below which balance cannot drop")
    target_budget_limit: Optional[int] = Field(default=None, sa_column=Column(BigInteger, nullable=True), description="Max wallet cap")
    auto_approve_threshold: int = Field(default=0, sa_column=Column(BigInteger), description="Max amount disburseable without voting")
    approval_timeout_hours: int = Field(default=24, description="Voting window hours before spend request cancels")
    timelock_duration_hours: int = Field(default=0, description="Holding delay hours after approval before dispatch")

    # Velocity Controls
    daily_spending_cap: Optional[int] = Field(default=None, sa_column=Column(BigInteger, nullable=True), description="Max 24h spend cap")
    per_transaction_cap: Optional[int] = Field(default=None, sa_column=Column(BigInteger, nullable=True), description="Max single spend cap")
    allowed_disbursement_types: str = Field(
        default='["MEMBER_ACCOUNTS", "EXTERNAL_PAYEES"]',
        description="JSON array of allowed recipient types"
    )

    # Live Wallet State
    current_balance: int = Field(default=0, sa_column=Column(BigInteger))
    total_deposited: int = Field(default=0, sa_column=Column(BigInteger))
    total_spent: int = Field(default=0, sa_column=Column(BigInteger))
    is_active: bool = Field(default=True)

    updated_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
