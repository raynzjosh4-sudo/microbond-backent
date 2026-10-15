from pydantic import BaseModel, Field
from typing import Optional

class PayDuesRequest(BaseModel):
    cycles_count: int = Field(default=1, ge=1, description="Number of billing cycles to pay for (supports advance payment)")
    note: Optional[str] = Field(default=None, max_length=200)
