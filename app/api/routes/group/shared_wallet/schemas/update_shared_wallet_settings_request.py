from typing import Optional, List
from pydantic import BaseModel, Field

class UpdateSharedWalletSettingsRequest(BaseModel):
    minimum_balance_floor: Optional[int] = Field(
        default=None, ge=0,
        description="Reserve balance below which the wallet cannot be depleted"
    )
    target_budget_limit: Optional[int] = Field(
        default=None, ge=0,
        description="Maximum wallet ceiling balance. Null = unlimited"
    )
    auto_approve_threshold: Optional[int] = Field(
        default=None, ge=0,
        description="Spending amount that can be disbursed without triggering a member approval vote"
    )
    approval_timeout_hours: Optional[int] = Field(
        default=None, ge=1, le=168,
        description="Hours before a pending spend proposal expires"
    )
    timelock_duration_hours: Optional[int] = Field(
        default=None, ge=0, le=168,
        description="Holding window in hours before approved funds are disbursed"
    )
    daily_spending_cap: Optional[int] = Field(
        default=None, ge=0,
        description="Maximum total spending allowed in a 24-hour window. Null = unlimited"
    )
    per_transaction_cap: Optional[int] = Field(
        default=None, ge=0,
        description="Maximum single transaction amount. Null = unlimited"
    )
    allowed_disbursement_types: Optional[List[str]] = Field(
        default=None,
        description="Allowed recipients, e.g. ['MEMBER_ACCOUNTS', 'EXTERNAL_PAYEES']"
    )
