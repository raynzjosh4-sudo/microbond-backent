from typing import List, Optional
from pydantic import BaseModel, Field

class RingStatus(BaseModel):
    """
    Drives the segmented progress arc around the group's avatar in Jetpack Compose:
    - paid_on_time_count: Green arc
    - missed_deadline_count: Red arc
    - (total - paid - missed): Pending neutral arc
    """
    total_expected_members: int = Field(default=0, ge=0)
    paid_on_time_count: int = Field(default=0, ge=0)
    missed_deadline_count: int = Field(default=0, ge=0)

class ActionMessage(BaseModel):
    """
    Drives the animated vertical ticker text below each group title.
    Cycles automatically in Compose every 4-5 seconds.
    """
    text: str
    type: str  # e.g., "PAYOUT_TURN", "RECENT_CONTRIBUTION", "GOAL_PROGRESS", "SYSTEM_ALERT"
    has_blue_ticks: bool = True
    is_alert: bool = False

class GroupListSummaryResponse(BaseModel):
    """
    Full summary object delivered to the Android Dashboard screen.
    """
    group_id: str
    group_name: str
    group_type: str
    avatar_url: Optional[str] = None
    
    # Visual Progress Ring
    ring_status: RingStatus
    
    # Animated Ticker Messages
    action_messages: List[ActionMessage] = Field(default_factory=list)
    
    # Badges & Timestamps
    unread_count: int = Field(default=0, ge=0)
    last_activity_timestamp: int # Epoch ms
