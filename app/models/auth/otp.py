from app.models.auth.otp_record import OTPRecord
from pydantic import BaseModel
from typing import Optional

class OTPRequest(BaseModel):
    phone_number: str

class OTPVerify(BaseModel):
    phone_number: str
    code: str
    device_id: Optional[str] = None

__all__ = ["OTPRecord", "OTPRequest", "OTPVerify"]
