from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

class PayoutOrderStrategy(str, Enum):
    ADMIN_ASSIGNED = "Admin Assigned"
    RANDOMIZED = "Randomized by App"
    TRUST_SCORE = "Trust Score Ranked"

class RotatingGroupCreateRequest(BaseModel):
    name: str = Field(..., description="Name of the savings group")
    description: str = Field(default="", description="Optional description")
    group_image_url: str = Field(..., description="URL of the uploaded group image")
    type: str = Field(..., description="e.g. MERRY_GO_ROUND, GOAL_SAVINGS")
    payment_mode: str = Field(default="OBLIGATION")
    visibility: str = Field(default="PRIVATE")
    currency: str = Field(default="UGX")
    created_by_phone: str = Field(..., description="Phone number of the creator (for auth)")
    
    # Financials & Timing
    contribution_amount: float = Field(..., description="Exact amount e.g., 10000")
    maximum_member_capacity: int = Field(..., ge=3, description="Must be a whole number, e.g. 20")
    payouts_per_cycle: int = Field(..., ge=1, description="Members paid per cycle, e.g. 1")
    collection_days_interval: int = Field(default=7, description="Number of days to pass between collections")
    group_start_time: str = Field(..., description="Exact datetime or specific day the group kicks off")
    
    # Strategy & Overrides
    payout_order_strategy: PayoutOrderStrategy = Field(..., description="Must be selected by user")
    admin_assigned_order: Optional[List[int]] = Field(
        default=None, 
        description="Ordered list of user IDs from 1st to last"
    )
    
    # Risk Controls (Must be set)
    minimum_kyc_tier: int = Field(..., ge=1, le=3)
    require_guarantor: bool = Field(...)
    guarantor_default_action: str = Field(...)
    allow_partial_payments: bool = Field(...)
    allow_advance_deposits: bool = Field(...)
    enforce_payout_holds: bool = Field(...)
