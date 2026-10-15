from typing import Optional
from pydantic import BaseModel, Field, model_validator

class WelfareFundGroupCreateRequest(BaseModel):
    # Group identity
    name: str = Field(..., min_length=2, max_length=100)
    description: str = Field(default="", max_length=500)
    group_image_url: str = Field(..., description="Group/campaign profile image URL")
    visibility: str = Field(default="PRIVATE", description="PUBLIC or PRIVATE")
    currency: str = Field(default="UGX")

    # --- WelfareFundConfig fields (locked at creation) ---
    contribution_amount: int = Field(..., gt=0, description="Mandatory premium every member pays per cycle")
    collection_frequency_days: int = Field(default=30, ge=1, description="7=Weekly, 30=Monthly")
    waiting_period_days: int = Field(default=30, ge=0, description="Days a new member waits before they can claim")
    max_claim_amount_per_incident: int = Field(..., gt=0, description="Max amount for a single emergency claim")
    annual_claim_limit_per_member: int = Field(..., gt=0, description="Max total claims one member receives per year")
    payout_destination_type: str = Field(default="MEMBER_ACCOUNT", description="MEMBER_ACCOUNT or EXTERNAL_SERVICE")
    requires_documentary_evidence: bool = Field(default=True, description="Member must upload proof before claim is submitted")
    claim_approval_policy: str = Field(default="MAJORITY_VOTE", description="ADMIN_ONLY, WELFARE_COMMITTEE, MAJORITY_VOTE")

    @model_validator(mode="after")
    def validate_fields(self) -> "WelfareFundGroupCreateRequest":
        valid_policies = {"ADMIN_ONLY", "WELFARE_COMMITTEE", "MAJORITY_VOTE"}
        if self.claim_approval_policy not in valid_policies:
            raise ValueError(f"claim_approval_policy must be one of {valid_policies}")
        if self.annual_claim_limit_per_member < self.max_claim_amount_per_incident:
            raise ValueError("annual_claim_limit_per_member must be >= max_claim_amount_per_incident")
        return self
