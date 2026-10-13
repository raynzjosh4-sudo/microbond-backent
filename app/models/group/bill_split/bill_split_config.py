from typing import Optional
from sqlmodel import SQLModel, Field
import uuid
from sqlalchemy import Column, BigInteger
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class BillSplitConfig(SQLModel, table=True):
    """
    IMMUTABLE Group Creation Configuration for BILL_SPLIT groups.
    Defines the baseline terms of the split expense agreed upon at creation time.
    """
    __tablename__ = "billsplitconfig"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", unique=True, index=True)

    # Core Bill Terms
    total_bill_amount: int = Field(sa_column=Column(BigInteger), description="Total amount of the bill in smallest currency unit")
    split_mode: str = Field(default="EQUAL", description="EQUAL, EXACT, PERCENTAGE, BY_SHARES")
    settlement_deadline: Optional[int] = Field(default=None, sa_column=Column(BigInteger), description="Epoch ms by which all members must settle")
    bill_category: str = Field(default="GENERAL", description="GENERAL, DINING, TRAVEL, UTILITIES, RENT, ENTERTAINMENT")

    # Settlement Destination & Payee
    payout_destination_type: str = Field(default="ORGANIZER_WALLET", description="ORGANIZER_WALLET, MERCHANT_TILL, BILLER_DIRECT")
    payee_identifier: Optional[str] = Field(default=None, description="Merchant till number, phone number, or bill account number")
    payee_name: Optional[str] = Field(default=None, description="Display name of payee or vendor (e.g., 'Café Javas')")
    bill_receipt_url: Optional[str] = Field(default=None, description="URL to bill receipt or invoice photo")

    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
