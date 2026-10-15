from typing import Optional
from pydantic import BaseModel, Field, model_validator

class FundraiserGroupCreateRequest(BaseModel):
    # Basic group info
    name: str = Field(..., min_length=2, max_length=100, description="Name of the fundraiser")
    description: str = Field(default="", max_length=500, description="Short description of the cause")
    group_image_url: str = Field(..., description="URL of the uploaded group/campaign image")
    visibility: str = Field(default="PUBLIC", description="PUBLIC or PRIVATE")
    currency: str = Field(default="UGX", description="Currency for all donations")

    # --- FundraiserCampaignConfig fields (locked after creation) ---

    # 1. Campaign Target & Timeline
    target_amount: int = Field(
        default=0, ge=0,
        description="Total amount to raise in whole currency units. Set to 0 for an open-ended campaign."
    )
    campaign_deadline: Optional[int] = Field(
        default=None,
        description="When donations stop, as epoch ms timestamp. Leave null for no deadline."
    )

    # 2. Where the Money Goes
    payout_destination_type: str = Field(
        default="NOMINATED_ACCOUNT",
        description="NOMINATED_ACCOUNT (one account) or SPLIT_EQUALLY (share among members)"
    )
    nominated_account_id: Optional[str] = Field(
        default=None,
        description="ID of the verified payout account. Required when payout_destination_type is NOMINATED_ACCOUNT."
    )

    # 3. How the Money is Released
    payout_trigger_mode: str = Field(
        default="MANUAL",
        description="MANUAL (admin releases manually) or AUTO_ON_DEADLINE (auto-released when deadline passes)"
    )
    require_multi_signoff: bool = Field(
        default=False,
        description="Require multiple admins to approve before money is released."
    )
    signoff_count_required: int = Field(
        default=1, ge=1, le=10,
        description="How many signers must approve. Only used when require_multi_signoff is True."
    )

    @model_validator(mode="after")
    def validate_nominated_account(self) -> "FundraiserGroupCreateRequest":
        if self.payout_destination_type == "NOMINATED_ACCOUNT" and not self.nominated_account_id:
            raise ValueError(
                "nominated_account_id is required when payout_destination_type is NOMINATED_ACCOUNT."
            )
        return self
