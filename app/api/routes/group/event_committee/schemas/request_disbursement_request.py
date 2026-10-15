from typing import Optional
from pydantic import BaseModel, Field

class RequestDisbursementRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Amount to send to vendor or treasurer")
    recipient_name: str = Field(..., min_length=2, max_length=100, description="Vendor or recipient name")
    recipient_identifier: str = Field(..., description="Vendor mobile money / account number")
    reason: str = Field(..., min_length=3, max_length=500, description="Purpose of this payment (e.g. Venue Deposit)")
    invoice_reference: Optional[str] = Field(default=None, description="Reference ID of the uploaded invoice image")
