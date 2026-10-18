from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime
import uuid
from app.utils.time.now_utc_datetime import now_utc_datetime

def utc_now():
    return now_utc_datetime()

class User(SQLModel, table=True):
    # Core Identity
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    firebase_uid: Optional[str] = Field(default=None, index=True, unique=True)
    phone_number: str = Field(index=True, unique=True)
    full_name: Optional[str] = Field(default=None)
    
    # Profile Customization
    avatar_color: Optional[str] = Field(default="Gray")
    profile_picture_url: Optional[str] = Field(default=None)
    about_status: str = Field(default="Hey there! I am using Microbond.")
    default_currency: str = Field(default="UGX")

    # Personal Privacy Settings ("EVERYONE", "MY_CONTACTS", "NOBODY")
    profile_photo_visibility: str = Field(default="EVERYONE", description="Who can see my profile photo: EVERYONE, MY_CONTACTS, NOBODY")
    about_visibility: str = Field(default="EVERYONE", description="Who can see my about bio: EVERYONE, MY_CONTACTS, NOBODY")
    group_add_permission: str = Field(default="EVERYONE", description="Who can add me to groups: EVERYONE, MY_CONTACTS, NOBODY")
    
    # Statuses
    kyc_status: str = Field(default="UNVERIFIED")
    kyc_tier: int = Field(default=0)
    trust_score: int = Field(default=0)
    is_verified: bool = Field(default=False)
    is_phone_verified: bool = Field(default=True)
    is_profile_complete: bool = Field(default=False)
    
    # App Lock / Passcode
    hashed_pin: Optional[str] = Field(default=None)
    
    # Session / Presence
    fcm_token: Optional[str] = Field(default=None)
    is_online: bool = Field(default=False)
    last_seen_at: Optional[int] = Field(default=None) # Epoch ms
    
    # Security & Fraud Prevention (SIM-Swap Defense)
    primary_device_id: Optional[str] = Field(default=None, description="Hardware fingerprint to detect account takeovers")
    security_cooldown_until: Optional[int] = Field(default=None, description="Epoch ms until withdrawals/payouts unlock after a device swap")
    
    # Invite System
    referral_code: Optional[str] = Field(default=None, unique=True, index=True)
    referred_by_code: Optional[str] = Field(default=None)
    total_referrals: int = Field(default=0)
    total_earned: float = Field(default=0.0)
    
    # Tiering & Family/Guardian Linkage (Legacy compatibility)
    guardian_id: Optional[uuid.UUID] = Field(default=None, foreign_key="user.id")
    is_dependent_account: bool = Field(default=False)
    daily_withdrawal_limit: float = Field(default=50000.0)
    
    created_at: datetime = Field(default_factory=now_utc_datetime)
