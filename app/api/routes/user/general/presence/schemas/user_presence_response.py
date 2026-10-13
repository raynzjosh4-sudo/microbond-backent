from typing import Optional
from pydantic import BaseModel


class UserPresenceResponse(BaseModel):
    user_id: str
    full_name: Optional[str]
    is_online: bool
    last_seen_at: Optional[int]
    last_seen_formatted: str
