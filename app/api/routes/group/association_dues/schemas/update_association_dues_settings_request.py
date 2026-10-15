from pydantic import BaseModel, Field
from typing import Optional

class UpdateAssociationDuesSettingsRequest(BaseModel):
    auto_sweep_trigger: Optional[str] = Field(default=None, description="INSTANT, END_OF_CYCLE, or MANUAL_WITHDRAWAL")
    allow_advance_payments: Optional[bool] = Field(default=None)
    allow_installments: Optional[bool] = Field(default=None, description="Allow members to pay dues in installments / partial amounts")
    grace_period_days: Optional[int] = Field(default=None, ge=0)
    late_fee_amount: Optional[int] = Field(default=None, ge=0)
    arrears_action: Optional[str] = Field(default=None, description="SUSPEND_MEMBERSHIP or EXPEL_AFTER_LIMIT")
    max_missed_cycles_allowed: Optional[int] = Field(default=None, ge=1)
    show_defaulters_publicly: Optional[bool] = Field(default=None)
    treasury_ledger_visibility: Optional[str] = Field(default=None, description="TRANSPARENT or ADMIN_ONLY")

    # Arrears Policy & Reminders
    send_arrears_reminders: Optional[bool] = Field(default=None)
    arrears_reminder_days_before: Optional[int] = Field(default=None, ge=1)
    restrict_voting_on_arrears: Optional[bool] = Field(default=None)
    restrict_welfare_claims_on_arrears: Optional[bool] = Field(default=None)
