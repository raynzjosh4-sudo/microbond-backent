from typing import Optional
from pydantic import BaseModel, Field

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
