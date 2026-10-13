from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now_epoch():
    return now_epoch_ms()

class UserPaymentMethod(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)

    # e.g., "MTN Mobile Money", "Airtel Money"
    provider_name: str

    # The actual phone number or bank account number
    account_number: str
    account_name: Optional[str] = Field(default=None, description="Account holder name or verified name")

    # Verification fields — populated by PayoutAccountVerificationService
    account_type: str = Field(default="MOBILE_MONEY", description="'MOBILE_MONEY' or 'BANK_ACCOUNT'")
    is_verified: bool = Field(default=False, description="Whether the account was confirmed by an external provider")
    verified_name: Optional[str] = Field(default=None, description="Name returned by MTN / Airtel")
    verification_type: Optional[str] = Field(default=None, description="'MTN' | 'AIRTEL' | 'MANUAL'")

    is_default: bool = Field(default=False)
    created_at: int = Field(default_factory=utc_now_epoch, sa_column=Column(BigInteger))
