from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
import uuid

def utc_now_epoch():
    return int(datetime.now(timezone.utc).timestamp())

class UserPaymentMethod(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    
    # e.g., "MTN Mobile Money", "Airtel Money", "Visa", "Mastercard", "Bank Transfer"
    provider_name: str 
    
    # The actual phone number, card number, or bank account number
    account_number: str 
    
    account_name: str = Field(description="The registered name on the account")
    
    # Additional data like expiry date for cards could be added here later
    
    is_default: bool = Field(default=False)
    created_at: int = Field(default_factory=utc_now_epoch)
