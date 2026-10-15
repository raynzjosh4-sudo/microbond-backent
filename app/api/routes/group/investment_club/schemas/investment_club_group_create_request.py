from pydantic import BaseModel, Field, model_validator

class InvestmentClubGroupCreateRequest(BaseModel):
    # Group identity
    name: str = Field(..., min_length=2, max_length=100, description="Name of the investment club")
    description: str = Field(default="", max_length=500)
    group_image_url: str = Field(..., description="Investment club logo or image URL")
    visibility: str = Field(default="PRIVATE", description="PUBLIC or PRIVATE")
    currency: str = Field(default="UGX")

    # --- InvestmentClubConfig fields (locked at creation) ---
    share_unit_price: int = Field(..., gt=0, description="Cost of a single share in smallest currency units (e.g. 50000 UGX)")
    equity_calculation_mode: str = Field(default="PROPORTIONAL_TO_SHARES", description="PROPORTIONAL_TO_SHARES or FIXED_EQUAL")
    voting_power_logic: str = Field(default="PROPORTIONAL", description="PROPORTIONAL or ONE_MEMBER_ONE_VOTE")
    payout_destination_type: str = Field(default="VERIFIED_BROKERS_ONLY", description="VERIFIED_BROKERS_ONLY or REGISTERED_ASSET_ACCOUNT")
    dividend_distribution_rule: str = Field(default="AUTO_PUSH_PROPORTIONAL", description="AUTO_PUSH_PROPORTIONAL or REINVEST_IN_VAULT")
    lock_in_period_days: int = Field(default=180, ge=0, description="Minimum days member capital is locked")
    liquidation_action: str = Field(default="LIQUIDATE_PROPORTIONAL", description="Action upon dissolution: LIQUIDATE_PROPORTIONAL")

    @model_validator(mode="after")
    def validate_rules(self) -> "InvestmentClubGroupCreateRequest":
        valid_modes = {"PROPORTIONAL_TO_SHARES", "FIXED_EQUAL"}
        if self.equity_calculation_mode not in valid_modes:
            raise ValueError(f"equity_calculation_mode must be one of {valid_modes}")
        valid_voting = {"PROPORTIONAL", "ONE_MEMBER_ONE_VOTE"}
        if self.voting_power_logic not in valid_voting:
            raise ValueError(f"voting_power_logic must be one of {valid_voting}")
        valid_payout = {"VERIFIED_BROKERS_ONLY", "REGISTERED_ASSET_ACCOUNT"}
        if self.payout_destination_type not in valid_payout:
            raise ValueError(f"payout_destination_type must be one of {valid_payout}")
        valid_dividend = {"AUTO_PUSH_PROPORTIONAL", "REINVEST_IN_VAULT"}
        if self.dividend_distribution_rule not in valid_dividend:
            raise ValueError(f"dividend_distribution_rule must be one of {valid_dividend}")
        return self
