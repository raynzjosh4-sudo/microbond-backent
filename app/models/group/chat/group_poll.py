from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class GroupPoll(SQLModel, table=True):
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    creator_id: uuid.UUID = Field(foreign_key="user.id")
    
    question: str = Field(max_length=500)
    options: str = Field(description="JSON serialized list of options")
    
    # E.g., 'KICK_MEMBER', 'APPROVE_LOAN', 'CUSTOM'
    poll_type: str = Field(default="CUSTOM") 
    
    status: str = Field(default="OPEN", description="OPEN, CLOSED, EXECUTED")
    
    expires_at: int = Field(sa_column=Column(BigInteger))
    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
