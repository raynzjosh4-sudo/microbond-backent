from typing import Optional
from pydantic import BaseModel, Field

class SubmitPledgeRequest(BaseModel):
    pledged_amount: int = Field(..., gt=0, description="Amount the member promises to deposit")
    note: Optional[str] = Field(default=None, max_length=200, description="Optional note about the pledge")
