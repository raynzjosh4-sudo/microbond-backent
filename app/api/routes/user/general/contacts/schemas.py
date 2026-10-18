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


class ContactMemberSummary(BaseModel):
    """
    Summary of a phone contact who belongs to a discoverable savings group.
    """
    user_id: str = Field(..., description="Unique UUID identifier of the contact member")
    phone_number: str = Field(..., description="Verified phone number in E.164 format")
    profile_name: str = Field(..., description="Public display name / full name")
    profile_picture_url: Optional[str] = Field(None, description="Profile avatar picture URL if set")
    avatar_color: Optional[str] = Field("Gray", description="Fallback avatar color theme")


class DiscoverableContactGroup(BaseModel):
    """
    Savings group discovered through mutual phone contacts with social proof.
    """
    group_id: str = Field(..., description="Unique UUID identifier of the savings group")
    name: str = Field(..., description="Name of the savings group")
    description: str = Field(default="", description="Group description")
    group_image_url: Optional[str] = Field(default="", description="Group avatar/banner image URL")
    type: str = Field(..., description="Group type, e.g. MERRY_GO_ROUND, GOAL_SAVINGS")
    payment_mode: str = Field(default="OBLIGATION", description="OBLIGATION, VOLUNTARY, MIXED")
    visibility: str = Field(default="PRIVATE", description="PUBLIC or PRIVATE")
    currency: str = Field(default="UGX", description="Currency symbol/code")
    member_count: int = Field(default=0, description="Total active member count")
    max_members: Optional[int] = Field(default=None, description="Maximum member limit")
    mutual_contacts_count: int = Field(default=0, description="Total phone contacts who are active members")
    contact_members: List[ContactMemberSummary] = Field(
        default_factory=list,
        description="Phone contacts who are active members of this group"
    )
