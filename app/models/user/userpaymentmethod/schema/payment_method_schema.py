from typing import Optional
from pydantic import BaseModel, Field

class CreatePaymentMethodRequest(BaseModel):
    provider_name: str = Field(..., description="Provider name (e.g. 'MTN', 'Airtel')")
    account_number: str = Field(..., description="Phone number (e.g. '0780670440')")
    account_type: Optional[str] = Field(default=None, description="Optional: 'MOBILE_MONEY' or 'BANK_ACCOUNT'. Auto-detected.")
    is_default: bool = Field(default=False, description="Set as default payment method")
    app_pin: Optional[str] = Field(default=None, description="Required only if user has an active App PIN")


class PaymentMethodResponse(BaseModel):
    id: str
    provider_name: str
    account_number: str
    account_name: Optional[str] = None    # Backward compatibility
    account_type: Optional[str] = None
    verified_name: Optional[str]          # Name returned by MTN / Airtel
    is_verified: bool
    is_default: bool
    masked_number: str
    verification_type: Optional[str]      # "MTN" | "AIRTEL" | "MANUAL"
