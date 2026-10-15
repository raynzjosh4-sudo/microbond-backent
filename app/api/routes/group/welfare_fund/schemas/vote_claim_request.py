from pydantic import BaseModel, Field

class VoteClaimRequest(BaseModel):
    vote: str = Field(..., description="APPROVE or REJECT")
