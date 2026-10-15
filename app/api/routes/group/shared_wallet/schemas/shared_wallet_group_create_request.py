from pydantic import BaseModel, Field, model_validator

class SharedWalletGroupCreateRequest(BaseModel):
    # Basic group info
    name: str = Field(..., min_length=2, max_length=100, description="Name of the shared wallet group")
    description: str = Field(default="", max_length=500, description="Short purpose or description of the wallet")
    group_image_url: str = Field(..., description="URL of the uploaded group profile image")
    visibility: str = Field(default="PRIVATE", description="PUBLIC or PRIVATE")
    currency: str = Field(default="UGX", description="Wallet currency, e.g. UGX")

    # --- SharedWalletConfig fields (set at creation) ---
    replenishment_mode: str = Field(
        default="FLEXIBLE",
        description="FLEXIBLE (top-up anytime) or SCHEDULED_QUOTA (mandatory cycle deposit)"
    )
    member_quota_amount: int = Field(
        default=0, ge=0,
        description="Required contribution per member per cycle if replenishment_mode is SCHEDULED_QUOTA"
    )
    collection_frequency_days: int = Field(
        default=0, ge=0,
        description="Top-up interval in days: 0=Flexible/Daily, 7=Weekly, 30=Monthly"
    )
    spending_signoff_policy: str = Field(
        default="ADMIN_ONLY",
        description="Approval policy: ADMIN_ONLY, ANY_MEMBER_WITH_APPROVAL, MAJORITY_VOTE, UNANIMOUS"
    )
    exit_payout_rule: str = Field(
        default="PROPORTIONAL_REMAINING",
        description="Remaining balance split rule: PROPORTIONAL_REMAINING, EQUAL_SPLIT, CONSENSUS_DISTRIBUTION"
    )
    track_individual_contributions: bool = Field(
        default=True,
        description="Track each member's personal deposits and spends"
    )
    minimum_kyc_tier: int = Field(
        default=1, ge=0, le=3,
        description="Minimum KYC tier required to join (1 = Phone verified, 2 = National ID)"
    )

    @model_validator(mode="after")
    def validate_quota(self) -> "SharedWalletGroupCreateRequest":
        if self.replenishment_mode == "SCHEDULED_QUOTA" and self.member_quota_amount <= 0:
            raise ValueError("member_quota_amount must be greater than 0 when replenishment_mode is SCHEDULED_QUOTA.")
        valid_policies = {"ADMIN_ONLY", "ANY_MEMBER_WITH_APPROVAL", "MAJORITY_VOTE", "UNANIMOUS"}
        if self.spending_signoff_policy not in valid_policies:
            raise ValueError(f"Invalid spending_signoff_policy. Must be one of {valid_policies}")
        valid_exit_rules = {"PROPORTIONAL_REMAINING", "EQUAL_SPLIT", "CONSENSUS_DISTRIBUTION"}
        if self.exit_payout_rule not in valid_exit_rules:
            raise ValueError(f"Invalid exit_payout_rule. Must be one of {valid_exit_rules}")
        return self
