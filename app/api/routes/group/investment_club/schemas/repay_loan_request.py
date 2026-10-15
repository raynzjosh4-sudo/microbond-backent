from pydantic import BaseModel, Field

class RepayLoanRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Amount to repay against loan")
