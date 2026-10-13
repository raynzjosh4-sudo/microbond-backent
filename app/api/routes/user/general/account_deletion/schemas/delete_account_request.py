from typing import Optional
from pydantic import BaseModel, Field


class DeleteAccountRequest(BaseModel):
    confirmation: str = Field(
        ..., description="Must type 'DELETE MY ACCOUNT' to confirm"
    )
    reason: Optional[str] = Field(
        default=None, description="Optional exit survey / reason for closure"
    )
    app_pin: Optional[str] = Field(
        default=None, description="Required if user has set an App PIN"
    )
