from typing import Optional
from pydantic import BaseModel, Field

class CreatePayoutDestinationRequest(BaseModel):
    provider_name: str = Field(..., description="Provider name (e.g. 'MTN', 'Airtel', 'Stanbic Bank Uganda')")
    account_number: str = Field(..., description="Phone number (e.g. '0780670440') or bank account number")
    account_type: Optional[str] = Field(default=None, description="Optional: 'MOBILE_MONEY' or 'BANK_ACCOUNT'. Auto-detected from provider.")
    bank_code: Optional[str] = Field(default=None, description="Optional: Prembly bank code. Auto-detected from bank name.")
    is_default: bool = Field(default=False, description="Whether to make this the default payout destination")
    app_pin: Optional[str] = Field(default=None, description="Required only if user has set an App PIN")


class PayoutDestinationResponse(BaseModel):
    id: str
    provider_name: str
    account_number: str
    account_name: Optional[str] = None  # Backward compatibility for mobile client
    account_type: Optional[str] = None
    verified_name: Optional[str]   # Name returned by external provider (MTN/Airtel/Prembly)
    is_verified: bool
    is_default: bool
    masked_number: str
    verification_type: Optional[str]  # "MTN" | "AIRTEL" | "PREMBLY_BANK" | "MANUAL"
