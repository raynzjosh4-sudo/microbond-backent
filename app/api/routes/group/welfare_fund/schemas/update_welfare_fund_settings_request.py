from typing import Optional
from pydantic import BaseModel, Field

class UpdateWelfareFundSettingsRequest(BaseModel):
    minimum_reserve_balance: Optional[int] = Field(default=None, ge=0)
    approval_timeout_hours: Optional[int] = Field(default=None, ge=1, le=168)
    missed_payment_action: Optional[str] = Field(default=None)
    enable_late_fees: Optional[bool] = Field(default=None)
    allow_annual_dividend_split: Optional[bool] = Field(default=None)
