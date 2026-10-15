from typing import Optional
from pydantic import BaseModel

class MemberShareStatus(BaseModel):
    user_id: str
    full_name: str
    phone_number: Optional[str] = None
    role: str
    assigned_amount: int
    amount_paid: int
    tip_paid: int
    remaining_owed: int
    is_settled: bool
    paid_at: Optional[int] = None
