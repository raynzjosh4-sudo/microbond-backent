from pydantic import BaseModel, Field

class BuySharesRequest(BaseModel):
    shares_count: int = Field(..., gt=0, description="Number of shares to purchase")
