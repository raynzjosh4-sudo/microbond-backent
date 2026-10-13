from typing import Optional
from pydantic import BaseModel, Field


class UpdateUserProfileRequest(BaseModel):
    full_name: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="New full name, e.g. 'SSENKINDU EMMANUEL'",
    )
    profile_picture_url: Optional[str] = Field(
        default=None, description="Direct URL to uploaded profile picture"
    )
    avatar_color: Optional[str] = Field(
        default=None,
        description="Profile fallback avatar color, e.g. 'Blue', 'Emerald'",
    )
    about_status: Optional[str] = Field(
        default=None, max_length=160, description="User status / bio message"
    )
