from typing import Optional
from pydantic import BaseModel, Field


class HeartbeatRequest(BaseModel):
    is_online: bool = Field(
        default=True,
        description="Whether user is currently actively viewing the app",
    )
    current_group_id: Optional[str] = Field(
        default=None, description="Optional active group chat screen ID"
    )
