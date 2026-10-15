from pydantic import BaseModel, Field
from typing import Optional

class DistributeDividendsRequest(BaseModel):
    total_profit_amount: int = Field(..., gt=0, description="Gross profit amount returned to the club")
    source_asset_name: str = Field(..., min_length=2, max_length=150, description="Name of the asset that yielded the return")
    note: Optional[str] = Field(default=None, max_length=300)
