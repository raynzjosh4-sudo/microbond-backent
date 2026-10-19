from typing import Optional, List, Any
from pydantic import BaseModel, Field

class ReplyToSummary(BaseModel):
    message_id: str
    sender_id: Optional[str] = None
    sender_name: Optional[str] = None
    text: Optional[str] = None
    media_type: Optional[str] = None

class ChatMessageItem(BaseModel):
    id: str
    client_message_id: Optional[str] = None
    group_id: str
    
    # Sender Profile Details
    sender_id: str
    sender_name: str
    sender_phone: Optional[str] = None
    sender_avatar_url: Optional[str] = None
    sender_avatar_color: str = "Teal"
    is_outgoing: bool = False
    
    # Message Content
    message_type: str = "TEXT"
    message_text: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    media_mime_type: Optional[str] = None
    media_size_bytes: Optional[int] = None
    media_duration_seconds: Optional[int] = None
    media_width: Optional[int] = None
    media_height: Optional[int] = None
    aspect_ratio: Optional[float] = None
    attachments: Optional[Any] = None
    
    # Quoted Reply Preview
    reply_to: Optional[ReplyToSummary] = None
    reply_to_message_id: Optional[str] = None
    
    # Read Receipt & Delivery Status (Ticks)
    status: str = "SENT"  # "SENT" (1 gray tick), "DELIVERED" (2 gray ticks), "READ" (2 blue ticks)
    read_count: int = 0
    is_read: bool = False  # True when read by others (Double Blue Ticks)
    is_read_by_me: bool = False
    
    created_at: int
    updated_at: int

class ChatMessagesListResponse(BaseModel):
    data: List[ChatMessageItem] = Field(default_factory=list)

class MarkMessagesReadRequest(BaseModel):
    message_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional list of message UUID strings to mark as read. If omitted or empty, marks all unread incoming messages in the group as read."
    )

class MarkMessagesReadResponse(BaseModel):
    status: str = "success"
    group_id: str
    marked_count: int
    read_at: int
