from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone

def utc_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)

class TargetSavingsGroupDetails(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)
    
    # Financial Goals
    goal_amount: float
    target_date: str
    savings_pace: str = Field(default="Flexible") # Weekly, Monthly, Flexible
    
    # Group Dynamics & Policies
    lock_funds: bool = Field(default=True)
    hide_leaderboard: bool = Field(default=False)
    allow_early_exits: bool = Field(default=False)
    overage_policy: str = Field(default="Keep in group wallet")
    
    # Incentives
    top_up_matching_amount: float = Field(default=0.0)
    
    # Computed / Tracked state
    progress_percent: float = Field(default=0.0)
    
    created_at: int = Field(default_factory=utc_now)
