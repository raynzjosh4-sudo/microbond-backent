from typing import Optional, Union, Any
from pydantic import BaseModel

class SendMessageRequest(BaseModel):
    client_message_id: str
    message_type: str = "TEXT" # TEXT, SYSTEM_EVENT, VOTE, MEDIA, or Chart Types (e.g. STAT_CANDLESTICK)
    message_text: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    media_mime_type: Optional[str] = None
    media_size_bytes: Optional[int] = None
    media_duration_seconds: Optional[int] = None
    reply_to_message_id: Optional[Union[str, int]] = None
    attachments: Optional[Any] = None
