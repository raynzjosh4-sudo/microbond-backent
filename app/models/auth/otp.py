from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
from typing import Optional

def utc_now():
    return datetime.now(timezone.utc)

class OTPRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    phone_number: str = Field(index=True)
    code: str
    is_used: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime = Field(default_factory=utc_now)

from pydantic import BaseModel

class OTPRequest(BaseModel):
    phone_number: str

class OTPVerify(BaseModel):
    phone_number: str
    code: str
