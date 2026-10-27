from typing import Optional
from pydantic import BaseModel

class DepositInfoResponse(BaseModel):
    group_id: str
    group_name: str
    group_type: str = "MERRY_GO_ROUND"
    required_base_amount: int
    expected_amount: int = 0
    accumulated_penalties: int = 0
    amount_already_paid: int = 0
    total_due: int
    remaining_due: int = 0
    minimum_partial_amount: int = 1000
    maximum_deposit_amount: Optional[int] = None
    allow_partial_pay: bool = False
    allow_overpay: bool = True
    cycle_number: int = 1
    due_date: Optional[int] = None
    currency: str = "UGX"
    member_prepaid_balance: int = 0

