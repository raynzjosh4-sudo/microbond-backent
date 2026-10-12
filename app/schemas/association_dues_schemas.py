from pydantic import BaseModel, Field, model_validator
from typing import Optional


class AssociationDuesGroupCreateRequest(BaseModel):
    # Group identity
    name: str = Field(..., min_length=2, max_length=100, description="Name of the association, union, or alumni network")
    description: str = Field(default="", max_length=500)
    group_image_url: str = Field(..., description="Association seal or logo URL")
    visibility: str = Field(default="PUBLIC", description="PUBLIC or PRIVATE")
    currency: str = Field(default="UGX")

    # --- AssociationDuesConfig fields (locked at creation) ---
    dues_amount: int = Field(..., gt=0, description="Mandatory recurring subscription fee in smallest currency units")
    billing_cycle_days: int = Field(default=30, ge=1, description="Cycle interval: 30=Monthly, 90=Quarterly, 365=Annually")
    billing_start_date: int = Field(..., description="When the first billing cycle officially commences (epoch ms)")
    treasury_account_id: str = Field(..., min_length=3, description="UUID of verified Bank or MoMo account belonging to the Association")
    enable_prorated_dues: bool = Field(default=True, description="Prorate dues for members joining mid-cycle")

    @model_validator(mode="after")
    def validate_rules(self) -> "AssociationDuesGroupCreateRequest":
        if self.billing_cycle_days < 1:
            raise ValueError("billing_cycle_days must be at least 1 day.")
        return self


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


class PayDuesRequest(BaseModel):
    cycles_count: int = Field(default=1, ge=1, description="Number of billing cycles to pay for (supports advance payment)")
    note: Optional[str] = Field(default=None, max_length=200)


class TriggerTreasurySweepRequest(BaseModel):
    amount: Optional[int] = Field(default=None, gt=0, description="Amount to sweep. If None, sweeps the entire vault balance.")
    reference_note: Optional[str] = Field(default=None, max_length=300, description="Purpose or reference for this sweep")


# --- Fee Exemption Schemas ---

class CreateDuesExemptionRequest(BaseModel):
    user_id: str = Field(..., description="UUID of the member to exempt")
    exemption_type: str = Field(default="TEMPORARY", description="TEMPORARY or PERMANENT")
    reason: str = Field(default="HARDSHIP", description="HARDSHIP, STUDENT, ELDER, HONORARY, SICKNESS, or OTHER")
    notes: Optional[str] = Field(default=None, max_length=500, description="Justification or evidence details")
    discount_percentage: int = Field(default=100, ge=1, le=100, description="100 for 100% full dues waiver, or partial waiver percentage")
    start_date: Optional[int] = Field(default=None, description="Epoch ms when exemption starts (defaults to now)")
    end_date: Optional[int] = Field(default=None, description="Epoch ms when exemption ends (required for TEMPORARY)")


class UpdateDuesExemptionRequest(BaseModel):
    exemption_type: Optional[str] = None
    reason: Optional[str] = None
    notes: Optional[str] = None
    discount_percentage: Optional[int] = Field(default=None, ge=1, le=100)
    end_date: Optional[int] = None
    is_active: Optional[bool] = None

