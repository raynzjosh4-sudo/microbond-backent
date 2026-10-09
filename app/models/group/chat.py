from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
from sqlalchemy import Column, BigInteger

def utc_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)

class GroupChatMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    
    # We use a string for sender_id so we can put UUIDs or "SYSTEM" for automated messages
    sender_id: str = Field(index=True) 
    
    message_type: str = Field(default="TEXT", description="TEXT, IMAGE, SYSTEM_EVENT, VOTE")
    message_text: str = Field(..., description="The actual text content")
    media_url: Optional[str] = Field(default=None, description="URL if an image or file is attached")
    
    # For WhatsApp-like features
    reply_to_message_id: Optional[int] = Field(default=None, foreign_key="groupchatmessage.id")
    is_deleted: bool = Field(default=False)
    
    created_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))
