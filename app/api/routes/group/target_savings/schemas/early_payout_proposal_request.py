from pydantic import BaseModel, Field

class EarlyPayoutProposalRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500, description="Reason for requesting to end savings early")
