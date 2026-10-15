from pydantic import BaseModel, Field

class RequestSpendBody(BaseModel):
    amount: int = Field(..., gt=0, description="Amount to spend in whole currency units")
    recipient_type: str = Field(..., description="MEMBER_ACCOUNT or EXTERNAL_PAYEE")
    recipient_identifier: str = Field(..., description="Phone number, account ID, or till number")
    recipient_name: str = Field(..., min_length=2, max_length=100, description="Name of the recipient / merchant")
    reason: str = Field(..., min_length=3, max_length=500, description="Reason or invoice memo for this expenditure")
