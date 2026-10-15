from typing import Optional
from pydantic import BaseModel, Field

class SubmitClaimRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Amount requested for the emergency")
    emergency_type: str = Field(..., min_length=3, max_length=100, description="e.g. Medical, Funeral, Accident")
    description: str = Field(..., min_length=10, max_length=1000, description="Brief description of the emergency")
    evidence_reference: Optional[str] = Field(default=None, description="Reference ID or URL of uploaded documentary proof")
