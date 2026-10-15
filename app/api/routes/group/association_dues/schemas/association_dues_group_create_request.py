from pydantic import BaseModel, Field, model_validator

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
