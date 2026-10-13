from pydantic import BaseModel, Field


class InitiateWithdrawalRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Amount in UGX (Integer)")
    destination_msisdn: str = Field(..., description="Phone number to receive funds")
    app_pin: str = Field(
        ...,
        min_length=4,
        max_length=8,
        description="User App PIN for transaction confirmation",
    )
