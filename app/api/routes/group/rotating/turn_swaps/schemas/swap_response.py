from pydantic import BaseModel
from uuid import UUID

class SwapResponse(BaseModel):
    swap_request_id: str
    requester_user_id: UUID
    target_user_id: UUID
    requester_cycle_number: int
    target_cycle_number: int
    status: str
