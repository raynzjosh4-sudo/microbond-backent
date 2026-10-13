from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class GroupPollVote(SQLModel, table=True):
    poll_id: uuid.UUID = Field(foreign_key="grouppoll.id", primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", primary_key=True)
    
    selected_option: str = Field()
    
    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
