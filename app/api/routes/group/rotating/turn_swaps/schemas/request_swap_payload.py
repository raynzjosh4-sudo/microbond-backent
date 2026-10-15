from pydantic import BaseModel
from uuid import UUID

class RequestSwapPayload(BaseModel):
    target_user_id: UUID
