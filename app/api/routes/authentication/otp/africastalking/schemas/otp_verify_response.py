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
