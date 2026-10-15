from typing import Optional, List
from pydantic import BaseModel
from .member_share_status import MemberShareStatus

class BillSplitDashboardResponse(BaseModel):
    group_id: str
    name: str
    description: str
    currency: str
    group_image_url: Optional[str] = None
    
    # Bill status
    total_bill_amount: int
    total_collected: int
    total_tip_collected: int
    remaining_balance: int
    progress_percentage: float
    is_settled: bool
    settled_at: Optional[int] = None
    
    # Bill terms
    split_mode: str
    bill_category: str
    settlement_deadline: Optional[int] = None
    deadline_hours_remaining: Optional[float] = None
    is_deadline_passed: bool = False
    
    # Payee
    payout_destination_type: str
    payee_identifier: Optional[str] = None
    payee_name: Optional[str] = None
    bill_receipt_url: Optional[str] = None
    
    # Settings
    allow_tip_or_extra: bool
    auto_close_on_settlement: bool
    
    # Member data
    current_user_standing: Optional[MemberShareStatus] = None
    members: List[MemberShareStatus]
