from typing import Optional, List
from pydantic import BaseModel, Field

class UpdateEventCommitteeSettingsRequest(BaseModel):
    allow_overfunding: Optional[bool] = Field(default=None)
    track_pledges: Optional[bool] = Field(default=None)
    minimum_contribution_amount: Optional[int] = Field(default=None, ge=0)
    member_quota_amount: Optional[int] = Field(default=None, ge=0)
    allow_guest_deposits: Optional[bool] = Field(default=None)
    allow_partial_disbursements: Optional[bool] = Field(default=None)
    signoff_trustee_user_ids: Optional[List[str]] = Field(default=None, description="User IDs required to approve payments")
