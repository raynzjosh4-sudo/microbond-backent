from pydantic import BaseModel
from typing import Optional

class SetPayoutDestinationRequest(BaseModel):
    payout_destination_id: Optional[str] = None
