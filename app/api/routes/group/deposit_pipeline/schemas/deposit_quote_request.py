from pydantic import BaseModel, Field

class DepositQuoteRequest(BaseModel):
    entered_amount: int = Field(..., gt=0, description="Amount user typed in UGX (Integer)")
