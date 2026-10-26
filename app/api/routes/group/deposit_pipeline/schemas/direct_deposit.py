from typing import Optional
from pydantic import BaseModel, Field

class DirectDepositRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Amount to deposit in group currency (e.g., 25000 UGX)")
    payment_method: Optional[str] = Field(default="TEST_SIMULATION", description="Payment method label (e.g., 'TEST_WALLET', 'MTN_MOMO', 'AIRTEL_MONEY')")
    notes: Optional[str] = Field(default=None, description="Optional note or reference")
    client_reference: Optional[str] = Field(default=None, description="Optional idempotency reference")

class DirectDepositResponse(BaseModel):
    status: str = "SUCCESS"
    message: str
    transaction_id: str
    reference_id: str
    group_id: str
    amount_deposited: int
    member_total_contributed: int
    cycle_number: int
    obligation_status: str
    group_total_balance: int
    ring_completion_fraction: float
    timestamp: int
    cycle_contribution_credited: Optional[int] = None
    advance_savings_credited: Optional[int] = None
    member_prepaid_balance: Optional[int] = None
