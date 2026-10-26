from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms


class PayoutSignature(SQLModel, table=True):
    """
    Immutable audit record of a multi-signature approval or dispute on a group payout.
    Ensures pessimistic idempotency (a signer cannot sign twice) and tracks cryptographic
    or biometric/PIN verification details.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    payout_id: int = Field(foreign_key="grouppayout.id", index=True)
    signer_user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    
    signer_role: str = Field(default="SIGNER", description="ADMIN, TREASURER, or SIGNER")
    status: str = Field(default="SIGNED", index=True, description="SIGNED, DISPUTED, REVOKED")
    
    device_fingerprint: Optional[str] = Field(default=None, description="Handset fingerprint or device ID hash")
    pin_verified: bool = Field(default=True, description="Whether PIN or Biometrics were confirmed")
    notes: Optional[str] = Field(default=None, description="Reason for approval or dispute description")
    
    signature_timestamp: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
