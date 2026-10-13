from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from datetime import datetime
from app.utils.time.now_utc_datetime import now_utc_datetime

class KycProfile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True, unique=True)
    
    current_tier: str = Field(default="TIER_0_UNVERIFIED")
    overall_status: str = Field(default="UNVERIFIED")
    rejection_reason: Optional[str] = Field(default=None)
    
    first_name: Optional[str] = Field(default=None)
    last_name: Optional[str] = Field(default=None)
    middle_name: Optional[str] = Field(default=None)
    gender: Optional[str] = Field(default=None)
    nin: Optional[str] = Field(default=None, unique=True, index=True)
    dob: Optional[str] = Field(default=None)
    document_id: Optional[str] = Field(default=None)
    photo_base64: Optional[str] = Field(default=None)
    
    # SIM Verification fields flattened (could also use JSON)
    sim_msisdn: Optional[str] = Field(default=None)
    sim_telecom_provider: Optional[str] = Field(default=None)
    sim_registered_name: Optional[str] = Field(default=None)
    is_mobile_money_active: bool = Field(default=False)
    is_sim_name_matched: bool = Field(default=False)
    sim_verified_at: Optional[int] = Field(default=None, sa_column=Column(BigInteger))
    
    # Telecom KYC & SIM-Swap Tripwire Fields
    last_known_sim_registration_timestamp: Optional[int] = Field(default=None, sa_column=Column(BigInteger), description="Epoch ms of the carrier SIM registration/swap")
    sim_swap_detected: bool = Field(default=False, description="True if a recent SIM change occurred at telecom level")
    last_carrier_subscriber_id: Optional[str] = Field(default=None, description="Carrier internal subscriber hash/identifier")
    
    updated_at: datetime = Field(default_factory=now_utc_datetime)
