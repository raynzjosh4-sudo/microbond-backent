from pydantic import BaseModel, Field
from typing import Optional

class ChangeRoleRequest(BaseModel):
    role: str = Field(..., description="Target role: MEMBER, TREASURER, ADMIN, MODERATOR")
    title: Optional[str] = Field(default=None, description="Custom display badge/title (e.g., 'Treasurer', 'Elder', 'Auditor')")
