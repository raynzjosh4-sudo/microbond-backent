from typing import Optional
from pydantic import BaseModel, Field

class UpdateFundraiserSettingsRequest(BaseModel):
    allow_overfunding: Optional[bool] = Field(
        default=None,
        description="Allow donations even after the target amount is reached."
    )
    stop_on_target_reached: Optional[bool] = Field(
        default=None,
        description="Auto-close the campaign the moment the target is reached."
    )
    minimum_donation_amount: Optional[int] = Field(
        default=None, ge=0,
        description="Smallest donation accepted (whole currency units, e.g. 500 UGX)."
    )
