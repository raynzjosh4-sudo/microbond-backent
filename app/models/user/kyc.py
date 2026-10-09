from typing import Optional
from sqlmodel import SQLModel, Field
import uuid
from datetime import datetime, timezone

def utc_now():
    return datetime.now(timezone.utc)

class KycProfile(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True, unique=True)
    
    current_tier: str = Field(default="TIER_0_UNVERIFIED")
    overall_status: str = Field(default="UNVERIFIED")
    rejection_reason: Optional[str] = Field(default=None)
    
    # SIM Verification fields flattened (could also use JSON)
    sim_msisdn: Optional[str] = Field(default=None)
    sim_telecom_provider: Optional[str] = Field(default=None)
    sim_registered_name: Optional[str] = Field(default=None)
    is_mobile_money_active: bool = Field(default=False)
    is_sim_name_matched: bool = Field(default=False)
    sim_verified_at: Optional[int] = Field(default=None)
    
    updated_at: datetime = Field(default_factory=utc_now)

class KycDocument(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    
    document_type: str = Field(description="NATIONAL_ID, PASSPORT, etc.")
    document_number: str
    
    front_image_path: str
    back_image_path: Optional[str] = Field(default=None)
    selfie_image_path: Optional[str] = Field(default=None)
    
    extracted_full_name: Optional[str] = Field(default=None)
    date_of_birth: Optional[str] = Field(default=None)
    
    status: str = Field(default="PENDING")
    rejection_reason: Optional[str] = Field(default=None)
    
    submitted_at: int = Field(default_factory=lambda: int(datetime.now(timezone.utc).timestamp() * 1000))
    verified_at: Optional[int] = Field(default=None)
    expiry_date: Optional[int] = Field(default=None)
