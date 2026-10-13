from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class GroupChatReadReceipt(SQLModel, table=True):
    """
    Tracks which users have read which messages in a group chat.
    Crucial for WhatsApp's 'Double Blue Tick' feature in group settings.
    """
    message_id: uuid.UUID = Field(foreign_key="groupchatmessage.id", primary_key=True)
    user_id: str = Field(primary_key=True)
    read_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
