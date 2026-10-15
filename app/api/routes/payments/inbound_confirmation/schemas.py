import uuid
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class InboundPaymentConfirmationPayload(BaseModel):
    event_id: str = Field(..., description="Unique event identifier from payment gateway")
    event_type: str = Field("payment.collection.success", description="Event type: payment.collection.success or payment.collection.failed")
    external_reference_id: str = Field(..., description="Telecom or gateway network reference ID (e.g. MTN/Airtel TX ID)")
    group_id: str = Field(..., description="Target group ID to credit pooled funds")
    user_id: uuid.UUID = Field(..., description="Microbond user ID who initiated the deposit")
    amount: int = Field(..., gt=0, description="Settled amount in UGX integer (e.g. 50000)")
    currency: str = Field(default="UGX", description="ISO currency code, defaults to UGX")
    provider: str = Field(default="MOBILE_MONEY", description="e.g. MTN_MOMO, AIRTEL_MONEY")
    source_account: Optional[str] = Field(default=None, description="Source account details (e.g. phone number or account ID)")
    obligation_id: Optional[int] = Field(default=None, description="Optional member obligation ID to mark paid")
    status: str = Field(default="SUCCESS", description="SUCCESS or FAILED")
    failure_reason: Optional[str] = Field(default=None, description="Reason if status is FAILED")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional payment provider metadata")


class InboundPaymentConfirmationResponse(BaseModel):
    status: str = Field(..., description="SUCCESS, DUPLICATE, or FAILED")
    message: str
    external_reference_id: str
    ledger_entry_id: Optional[str] = None
    group_id: str
    amount_credited: int
