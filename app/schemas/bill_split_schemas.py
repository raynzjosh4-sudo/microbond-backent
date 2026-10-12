from typing import Optional, List
from pydantic import BaseModel, Field
import uuid

# ── 1. Create Request ─────────────────────────────────────────────────────────

class MemberSplitAllocation(BaseModel):
    user_id: uuid.UUID
    assigned_amount: int = Field(..., gt=0, description="Amount assigned to this member in smallest currency unit")

class BillSplitCreateRequest(BaseModel):
    # Core group identity
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = Field(default="")
    group_image_url: Optional[str] = Field(default="")
    currency: str = Field(default="UGX")
    visibility: str = Field(default="PRIVATE")

    # Immutable Bill Config terms
    total_bill_amount: int = Field(..., gt=0, description="Total amount of the bill in smallest currency unit (e.g. UGX)")
    split_mode: str = Field(default="EQUAL", description="EQUAL, EXACT, PERCENTAGE, BY_SHARES")
    settlement_deadline: Optional[int] = Field(default=None, description="Epoch ms by which all members must settle")
    bill_category: str = Field(default="GENERAL", description="GENERAL, DINING, TRAVEL, UTILITIES, RENT, ENTERTAINMENT")

    # Payee & Settlement Routing
    payout_destination_type: str = Field(default="ORGANIZER_WALLET", description="ORGANIZER_WALLET, MERCHANT_TILL, BILLER_DIRECT")
    payee_identifier: Optional[str] = Field(default=None, description="Till number, merchant paybill, or phone number")
    payee_name: Optional[str] = Field(default=None, description="Vendor or recipient name (e.g. 'Café Javas')")
    bill_receipt_url: Optional[str] = Field(default=None, description="URL of receipt or invoice photo")

    # Optional custom allocations if split_mode != 'EQUAL'
    member_allocations: Optional[List[MemberSplitAllocation]] = Field(default=None)

    # Operational settings
    allow_tip_or_extra: bool = Field(default=True)
    auto_close_on_settlement: bool = Field(default=True)
    send_reminder_hours_before: int = Field(default=24, ge=1)
    enable_late_fees: bool = Field(default=False)
    late_fee_amount: int = Field(default=0, ge=0)
    grace_period_hours: int = Field(default=24, ge=0)


# ── 2. Settings Update ────────────────────────────────────────────────────────

class BillSplitSettingsUpdate(BaseModel):
    allow_tip_or_extra: Optional[bool] = None
    auto_close_on_settlement: Optional[bool] = None
    send_reminder_hours_before: Optional[int] = Field(default=None, ge=1)
    enable_late_fees: Optional[bool] = None
    late_fee_amount: Optional[int] = Field(default=None, ge=0)
    grace_period_hours: Optional[int] = Field(default=None, ge=0)


# ── 3. Pay Share Request ──────────────────────────────────────────────────────

class PayBillShareRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Payment amount in smallest currency unit")
    tip_amount: int = Field(default=0, ge=0, description="Optional extra tip or contingency buffer")
    payment_method_id: Optional[str] = None
    phone_number: Optional[str] = None


# ── 4. Dashboard & Status Schemas ─────────────────────────────────────────────

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
