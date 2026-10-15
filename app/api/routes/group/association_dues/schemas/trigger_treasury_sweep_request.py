from pydantic import BaseModel, Field
from typing import Optional

class TriggerTreasurySweepRequest(BaseModel):
    amount: Optional[int] = Field(default=None, gt=0, description="Amount to sweep. If None, sweeps the entire vault balance.")
    reference_note: Optional[str] = Field(default=None, max_length=300, description="Purpose or reference for this sweep")
