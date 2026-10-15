from pydantic import BaseModel

class DepositInfoResponse(BaseModel):
    group_id: str
    group_name: str
    required_base_amount: int
    accumulated_penalties: int
    amount_already_paid: int
    total_due: int
    allow_partial_pay: bool
    allow_overpay: bool
    currency: str = "UGX"
