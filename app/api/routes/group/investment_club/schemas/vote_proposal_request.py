from pydantic import BaseModel, Field

class VoteProposalRequest(BaseModel):
    vote: str = Field(..., description="APPROVE or REJECT")
