from pydantic import BaseModel, Field
from typing import Optional

class ApplyLoanRequest(BaseModel):
    principal_amount: int = Field(..., gt=0, description="Loan capital requested in smallest currency units")
    due_date: int = Field(..., description="Repayment deadline (epoch ms)")
    purpose: Optional[str] = Field(default=None, max_length=500)
