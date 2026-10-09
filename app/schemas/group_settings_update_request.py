from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class GroupSettingsUpdateRequest(BaseModel):
    requesting_phone: str = Field(description="Phone number of the user attempting to update settings (must be ADMIN).")
    hide_balances: Optional[bool] = None
    hide_member_contact: Optional[bool] = None
    invite_only: Optional[bool] = None
    approval_strategy: Optional[str] = None
    quorum_percentage: Optional[int] = None
    arrears_policy: Optional[str] = None
    enable_late_fees: Optional[bool] = None
    late_fee_amount: Optional[float] = None
    late_fee_frequency: Optional[str] = None
    enable_grace_period: Optional[bool] = None
    grace_period_duration: Optional[int] = None
    minimum_trust_score: Optional[int] = None
    require_guarantors: Optional[bool] = None
    guarantor_count: Optional[int] = None
    max_payout_active: Optional[bool] = None
    max_payout_limit: Optional[float] = None
    is_audit_active: Optional[bool] = None
    enable_escrow: Optional[bool] = None
    escrow_release_time: Optional[int] = None
    enable_timelock: Optional[bool] = None
    timelock_duration: Optional[int] = None
    member_visibility_overrides: Optional[Dict[str, Any]] = Field(default=None, description="JSON mapping setting keys to booleans (true if shared with members)")

class GroupSettingsUpdateResponse(BaseModel):
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None
