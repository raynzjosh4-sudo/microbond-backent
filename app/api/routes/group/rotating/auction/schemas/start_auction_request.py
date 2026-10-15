from pydantic import BaseModel, Field

class StartAuctionRequest(BaseModel):
    cycle_number: int = Field(default=1, ge=1, description="Cycle number for the payout auction")
    duration_minutes: int = Field(default=60, ge=1, le=10080, description="Auction duration in minutes (default 60)")
