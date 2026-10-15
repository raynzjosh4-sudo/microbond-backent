from typing import Optional
from pydantic import BaseModel

class DepositQuoteResponse(BaseModel):
    group_id: str
    deposit_amount: int
    transaction_fee: int
    sms_fee_ugx: int = 0          # Non-zero only if member has SMS opt-in
    total_to_charge: int
    quote_token: str
    validation_status: str = "VALIDATED"
    currency: str = "UGX"
    sms_fee_notice: Optional[str] = None
