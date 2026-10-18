from typing import Optional
from pydantic import BaseModel, Field


class UserPrivacySettingsResponse(BaseModel):
    status: str = Field(default="success")
    profile_photo_visibility: str = Field(
        ...,
        description="Who can see profile photo: EVERYONE, MY_CONTACTS, or NOBODY",
    )
    about_visibility: str = Field(
        ...,
        description="Who can see about status: EVERYONE, MY_CONTACTS, or NOBODY",
    )
    group_add_permission: str = Field(
        ...,
        description="Who can add to groups: EVERYONE, MY_CONTACTS, or NOBODY",
    )


class UpdateUserPrivacySettingsRequest(BaseModel):
    profile_photo_visibility: Optional[str] = Field(
        default=None,
        description="Who can see profile photo: 'Everyone', 'My contacts', or 'Nobody'",
    )
    about_visibility: Optional[str] = Field(
        default=None,
        description="Who can see about status: 'Everyone', 'My contacts', or 'Nobody'",
    )
    group_add_permission: Optional[str] = Field(
        default=None,
        description="Who can add to groups: 'Everyone', 'My contacts', or 'Nobody'",
    )
