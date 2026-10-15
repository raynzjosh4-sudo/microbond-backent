from pydantic import BaseModel, Field
from typing import Optional

class KickMemberRequest(BaseModel):
    reason: Optional[str] = Field(default="Removed by group administration", description="Explanation for audit log")
    ban: bool = Field(default=False, description="If true, marks status as BANNED preventing re-joining via invite link")
