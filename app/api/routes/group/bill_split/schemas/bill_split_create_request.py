from typing import Optional, List
from pydantic import BaseModel, Field
from .member_split_allocation import MemberSplitAllocation

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
