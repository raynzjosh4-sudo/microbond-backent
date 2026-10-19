from typing import List, Optional
from pydantic import BaseModel, Field
from .ring_status import RingStatus
from .action_message import ActionMessage
from .last_message_summary import LastMessageSummary

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
    last_activity_timestamp: int  # Epoch ms
    
    # Latest Chat Message Preview
    last_message: Optional[LastMessageSummary] = None

