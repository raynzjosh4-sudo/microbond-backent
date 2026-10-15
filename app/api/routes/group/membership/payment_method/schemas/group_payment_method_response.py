from pydantic import BaseModel
from typing import Optional

class GroupPaymentMethodResponse(BaseModel):
    payment_method_id: Optional[str]
    provider_name: str
    account_number: str
    account_name: Optional[str] = None
    verified_name: Optional[str] = None
    is_verified: Optional[bool] = None
    verification_type: Optional[str] = None
    masked_number: str
    is_fallback: bool
