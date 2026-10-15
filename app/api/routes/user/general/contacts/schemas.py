from typing import List, Optional
from pydantic import BaseModel, Field


class ContactSyncRequest(BaseModel):
    """
    Request model containing a batch of normalized phone numbers to cross-reference.
    """
    phone_numbers: List[str] = Field(
        default_factory=list,
        description="Array of normalized E.164 phone numbers extracted from the Android address book",
    )


class MatchedContact(BaseModel):
    """
    Safe public user profile returned when a phone number matches a registered Microbond user.
    """
    user_id: str = Field(..., description="Unique UUID identifier of the Microbond user")
    phone_number: str = Field(..., description="Verified phone number in E.164 format")
    profile_name: str = Field(..., description="Public display name / full name")
    profile_picture_url: Optional[str] = Field(None, description="Profile avatar picture URL if set")
    avatar_color: Optional[str] = Field("Gray", description="Fallback avatar color theme")
    about_status: Optional[str] = Field(None, description="About bio / status message")
