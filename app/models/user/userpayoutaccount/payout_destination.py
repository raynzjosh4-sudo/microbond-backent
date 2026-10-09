from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
import uuid

def utc_now_epoch():
    return int(datetime.now(timezone.utc).timestamp())

class UserPayoutDestination(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    provider_name: str = Field(description="e.g., MTN Mobile Money, Airtel Money")
    account_number: str = Field(description="The actual phone number or bank account number")
    account_name: str = Field(description="The registered name on the account")
    is_default: bool = Field(default=False)
    created_at: int = Field(default_factory=utc_now_epoch)
