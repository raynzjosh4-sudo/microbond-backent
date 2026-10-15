from typing import Optional
from pydantic import BaseModel, Field

class BillSplitSettingsUpdate(BaseModel):
    allow_tip_or_extra: Optional[bool] = None
    auto_close_on_settlement: Optional[bool] = None
    send_reminder_hours_before: Optional[int] = Field(default=None, ge=1)
    enable_late_fees: Optional[bool] = None
    late_fee_amount: Optional[int] = Field(default=None, ge=0)
    grace_period_hours: Optional[int] = Field(default=None, ge=0)
