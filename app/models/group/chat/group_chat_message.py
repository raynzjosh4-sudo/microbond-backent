from typing import Optional, List, Dict, Any
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger, String, Index, JSON, Float
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class GroupChatMessage(SQLModel, table=True):
    __table_args__ = (
        Index("ix_chat_group_active_created", "group_id", "is_deleted", "created_at"),
    )

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    
    # WhatsApp style: Client-generated UUID to prevent duplicate sends and track local status
    client_message_id: Optional[str] = Field(default=None, unique=True, index=True)
    
    group_id: str = Field(foreign_key="group.group_id", index=True)
    
    # We use a string for sender_id so we can put UUIDs or "SYSTEM" for automated messages
    sender_id: str = Field(index=True) 
    
    # Message Classification
    message_type: str = Field(default="TEXT", description="TEXT, MEDIA, SYSTEM_EVENT, VOTE")
    
    # Text content (acts as caption if media is attached)
    # Production: limited to 4000 chars to prevent DB bloat/DDoS
    message_text: Optional[str] = Field(
        default=None, 
        max_length=4000, 
        sa_column=Column(String(4000)),
        description="The actual text content or caption"
    )
    
    # Media specific fields (WhatsApp style)
    media_url: Optional[str] = Field(default=None, description="URL to the Cloudflare R2 storage")
    media_type: Optional[str] = Field(default=None, description="IMAGE, VIDEO, AUDIO, DOCUMENT, VOICE_NOTE")
    media_mime_type: Optional[str] = Field(default=None, description="e.g. image/jpeg, video/mp4")
    media_size_bytes: Optional[int] = Field(default=None, description="File size in bytes")
    media_duration_seconds: Optional[int] = Field(default=None, description="For audio/video playback length")
    media_width: Optional[int] = Field(default=None, description="Image/video pixel width")
    media_height: Optional[int] = Field(default=None, description="Image/video pixel height")
    aspect_ratio: Optional[float] = Field(default=None, description="Calculated aspect ratio (width / height)")

    # Multi-file gallery / albums (list of media objects with url, dimensions, ratio, mime, etc.)
    attachments: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="List of media attachments with URLs, dimensions, and aspect ratios"
    )
    
    # For WhatsApp-like features
    reply_to_message_id: Optional[uuid.UUID] = Field(default=None, foreign_key="groupchatmessage.id")
    
    # Status and State
    status: str = Field(default="SENT", description="SENT, DELIVERED, READ")
    is_deleted: bool = Field(default=False)
    
    # Production: Indexes on time fields for fast pagination and offline syncing
    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger, index=True))
    updated_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger, index=True))
