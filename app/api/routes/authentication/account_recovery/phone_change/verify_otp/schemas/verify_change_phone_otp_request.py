from pydantic import BaseModel


class VerifyChangePhoneOTPRequest(BaseModel):
    new_phone_number: str
    code: str
