from pydantic import BaseModel, Field
from typing import Optional

class CreateDuesExemptionRequest(BaseModel):
    user_id: str = Field(..., description="UUID of the member to exempt")
    exemption_type: str = Field(default="TEMPORARY", description="TEMPORARY or PERMANENT")
    reason: str = Field(default="HARDSHIP", description="HARDSHIP, STUDENT, ELDER, HONORARY, SICKNESS, or OTHER")
    notes: Optional[str] = Field(default=None, max_length=500, description="Justification or evidence details")
    discount_percentage: int = Field(default=100, ge=1, le=100, description="100 for 100% full dues waiver, or partial waiver percentage")
    start_date: Optional[int] = Field(default=None, description="Epoch ms when exemption starts (defaults to now)")
    end_date: Optional[int] = Field(default=None, description="Epoch ms when exemption ends (required for TEMPORARY)")
