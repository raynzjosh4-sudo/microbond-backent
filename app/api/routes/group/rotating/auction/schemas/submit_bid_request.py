from pydantic import BaseModel, Field

class SubmitBidRequest(BaseModel):
    bid_amount: float = Field(..., gt=0, description="The discount amount the user is bidding")
