from typing import List, Optional
from pydantic import BaseModel, Field

class RingStatus(BaseModel):
    """
    Drives the segmented progress arc around the group's avatar in Jetpack Compose:
    - paid_on_time_count: Green arc (SAVED / FULL)
    - partial_paid_count: Amber / Yellow arc (PARTIAL / HALF)
    - missed_deadline_count: Red arc (MISSED / LATE)
    - (total - paid - partial - missed): Pending neutral dark gray arc
    """
    total_expected_members: int = Field(default=0, ge=0)
    paid_on_time_count: int = Field(default=0, ge=0)
    partial_paid_count: int = Field(default=0, ge=0)
    missed_deadline_count: int = Field(default=0, ge=0)

    @property
    def ring_fraction(self) -> float:
        if self.total_expected_members <= 0:
            return 0.0
        return min(1.0, max(0.0, round(self.paid_on_time_count / self.total_expected_members, 4)))


class ActionMessage(BaseModel):
    """
    Drives the animated vertical ticker text below each group title.
    Cycles automatically in Compose every 4-5 seconds.
    """
    text: str
    type: str  # e.g., "PAYOUT_TURN", "RECENT_CONTRIBUTION", "GOAL_PROGRESS", "SYSTEM_ALERT"
    has_blue_ticks: bool = True
    is_alert: bool = False


class LastMessageSummary(BaseModel):
    """
    Summary of the most recent message in the group chat,
    used to render chat previews on the main group list.
    """
    message_id: Optional[str] = None
    sender_id: Optional[str] = None
    sender_name: Optional[str] = None
    text: Optional[str] = None  # Formatted preview text (e.g., "Hello", "📷 Photo")
    raw_text: Optional[str] = None  # Raw message text
    message_type: str = "TEXT"  # TEXT, MEDIA, SYSTEM_EVENT, VOTE
    media_type: Optional[str] = None  # IMAGE, VIDEO, AUDIO, DOCUMENT, VOICE_NOTE
    timestamp: int  # Epoch ms
    is_outgoing: bool = False
    status: str = "SENT"  # SENT, DELIVERED, READ


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


__all__ = [
    "RingStatus",
    "ActionMessage",
    "LastMessageSummary",
    "GroupListSummaryResponse",
]
