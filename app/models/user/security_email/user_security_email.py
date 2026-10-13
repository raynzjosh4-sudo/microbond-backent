from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
from datetime import datetime
import uuid
from app.utils.time.now_utc_datetime import now_utc_datetime

def utc_now():
    return now_utc_datetime()

class UserSecurityEmail(SQLModel, table=True):
    """
    Dedicated table for optional secondary/backup email addresses.
    Keeps the core User table clean and unencumbered.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True, unique=True, description="Owner of the backup email")
    
    email: str = Field(index=True, description="Secondary email address for alerts and account recovery")
    is_verified: bool = Field(default=False, description="Whether ownership of this email address has been verified")
    
    # Verification Security State
    verification_token: Optional[str] = Field(default=None, description="Current pending verification OTP/token")
    verification_expires_at: Optional[int] = Field(default=None, sa_column=Column(BigInteger, nullable=True), description="Epoch ms expiration for the verification code")
    
    created_at: datetime = Field(default_factory=now_utc_datetime)
    verified_at: Optional[datetime] = Field(default=None)
