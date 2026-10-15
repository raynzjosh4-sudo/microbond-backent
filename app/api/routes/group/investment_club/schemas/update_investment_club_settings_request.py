from pydantic import BaseModel, Field
from typing import Optional

class UpdateInvestmentClubSettingsRequest(BaseModel):
    minimum_purchase_quota: Optional[int] = Field(default=None, ge=0)
    proposal_approval_threshold_pct: Optional[int] = Field(default=None, ge=51, le=100)
    admin_management_fee_pct: Optional[int] = Field(default=None, ge=0, le=20)
    allow_internal_share_transfers: Optional[bool] = Field(default=None)
    enable_late_fees: Optional[bool] = Field(default=None)

    # Investment Rules & Member Borrowing
    interest_rate_mode: Optional[str] = Field(default=None, description="GROUP_VOTE or FIXED_PERCENTAGE")
    fixed_interest_rate_pct: Optional[float] = Field(default=None)
    require_loan_guarantors: Optional[bool] = Field(default=None)
    min_loan_guarantors: Optional[int] = Field(default=None, ge=0)
    max_borrowing_limit: Optional[int] = Field(default=None, ge=0)
    early_repayment_discount_pct: Optional[float] = Field(default=None, ge=0.0)
    new_share_issuance_mode: Optional[str] = Field(default=None)
    default_recovery_action: Optional[str] = Field(default=None)

    # Fund Stability, Liquidity & Reminders
    contribution_reminder_days_before: Optional[int] = Field(default=None, ge=1)
    auto_debit_consent_required: Optional[bool] = Field(default=None)
    emergency_contact_name: Optional[str] = Field(default=None)
    emergency_contact_phone: Optional[str] = Field(default=None)
    liquidity_buffer_coverage_pct: Optional[int] = Field(default=None, ge=0, le=100)
    enable_late_fee_escalation: Optional[bool] = Field(default=None)
    enable_sms_call_reminders: Optional[bool] = Field(default=None)
