from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional
from app.utils.time.now_utc_datetime import now_utc_datetime

class OTPRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    phone_number: str = Field(index=True, max_length=30)
    code_hash: str = Field(index=True, max_length=128)
    is_used: bool = Field(default=False, index=True)
    attempts: int = Field(default=0)
    created_at: datetime = Field(default_factory=now_utc_datetime, index=True)
    expires_at: datetime = Field(index=True)
