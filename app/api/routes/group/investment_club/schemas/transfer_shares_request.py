from pydantic import BaseModel, Field

class TransferSharesRequest(BaseModel):
    recipient_user_id: str = Field(..., description="UUID of the active club member receiving the shares")
    shares_count: int = Field(..., gt=0, description="Number of shares to transfer")
