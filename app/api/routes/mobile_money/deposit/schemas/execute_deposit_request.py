from typing import Optional
from pydantic import BaseModel, Field


class ExecuteDepositRequest(BaseModel):
    phone_number: str = Field(..., description="Ugandan Mobile Money phone number (e.g. 0771234567 or 256701234567)")
    total_to_charge: int = Field(..., gt=0, description="Total amount to charge including fees (UGX Integer)")
    quote_token: Optional[str] = Field(default=None, description="Layer 2 validated quote token")
    group_id: str = Field(..., description="Target group ID")
