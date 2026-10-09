from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field
from pydantic import BaseModel

def get_utcnow():
    return datetime.now(timezone.utc)

class OTPRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    phone_number: str = Field(index=True)
    code: str
    expires_at: datetime
    is_used: bool = Field(default=False)
    created_at: datetime = Field(default_factory=get_utcnow)

class OTPRequest(BaseModel):
    phone_number: str

class OTPVerify(BaseModel):
    phone_number: str
    code: str
