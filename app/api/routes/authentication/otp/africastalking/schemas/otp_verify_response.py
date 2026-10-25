import uuid
from pydantic import BaseModel


class OTPVerifyResponse(BaseModel):
    status: str
    access_token: str
    token_type: str = "bearer"
    user_id: uuid.UUID | None
    phone_number: str
    is_new_user: bool
    is_profile_complete: bool
    has_app_pin: bool = False
    full_name: str | None = None
    avatar_url: str | None = None
    profile_picture_url: str | None = None
    avatar_color: str | None = None
    about_status: str | None = None
