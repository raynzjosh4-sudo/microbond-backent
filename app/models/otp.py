from pydantic import BaseModel
from app.models.auth.otp_record import OTPRecord

class OTPRequest(BaseModel):
    phone_number: str

class OTPVerify(BaseModel):
    phone_number: str
    code: str
