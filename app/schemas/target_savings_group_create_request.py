from pydantic import BaseModel, Field
from typing import Optional

class TargetSavingsGroupCreateRequest(BaseModel):
    name: str = Field(..., description="Name of the savings group")
    description: str = Field(default="", description="Optional description")
    group_image_url: str = Field(..., description="URL of the uploaded group image")
    type: str = Field(default="GOAL_SAVINGS", description="Group type")
    payment_mode: str = Field(default="OBLIGATION")
    visibility: str = Field(default="PRIVATE")
    currency: str = Field(default="UGX")
    created_by_phone: str = Field(..., description="Phone number of the creator (for auth)")
    
    # Financial Goals
    goal_amount: float = Field(..., description="Target amount to save")
    target_date: str = Field(..., description="When the goal should be reached")
    savings_pace: str = Field(default="Flexible", description="Weekly, Monthly, Flexible")
    
    # Group Dynamics & Policies
    lock_funds: bool = Field(default=True)
    hide_leaderboard: bool = Field(default=False)
    allow_early_exits: bool = Field(default=False)
    overage_policy: str = Field(default="Keep in group wallet")
    
    # Incentives
    top_up_matching_amount: float = Field(default=0.0)
