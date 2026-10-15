from pydantic import BaseModel, Field
from typing import Optional

class ReviewLoanRequest(BaseModel):
    status: str = Field(..., description="APPROVED or REJECTED")
    rejection_reason: Optional[str] = Field(default=None)
