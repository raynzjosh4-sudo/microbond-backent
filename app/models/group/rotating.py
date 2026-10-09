from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone

def utc_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)

class RotatingGroupDetails(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)
    
    contribution_amount: float
    payouts_per_cycle: int
    number_of_cycles: int # Automatically calculated (e.g. math.ceil(max_members / payouts_per_cycle))
    collection_days_interval: int
    group_start_time: str
    
    payout_order_strategy: str
    is_payout_order_locked: bool = Field(default=False)
    
    # Calculated Rules
    total_expected_pool_per_cycle: float
    
    # Risk Controls
    minimum_kyc_tier: int
    require_guarantor: bool
    guarantor_default_action: str
    allow_partial_payments: bool
    allow_advance_deposits: bool
    enforce_payout_holds: bool
    
    current_cycle: int = Field(default=1)
    created_at: int = Field(default_factory=utc_now)
