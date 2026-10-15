from typing import Optional
from pydantic import BaseModel, Field

class PayBillShareRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Payment amount in smallest currency unit")
    tip_amount: int = Field(default=0, ge=0, description="Optional extra tip or contingency buffer")
    payment_method_id: Optional[str] = None
    phone_number: Optional[str] = None
