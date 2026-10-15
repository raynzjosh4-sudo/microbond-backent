from pydantic import BaseModel, Field
from typing import Optional

class UpdateDuesExemptionRequest(BaseModel):
    exemption_type: Optional[str] = None
    reason: Optional[str] = None
    notes: Optional[str] = None
    discount_percentage: Optional[int] = Field(default=None, ge=1, le=100)
    end_date: Optional[int] = None
    is_active: Optional[bool] = None
