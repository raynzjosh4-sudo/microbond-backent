from pydantic import BaseModel


class VerifyChangePhoneOTPResponse(BaseModel):
    status: str
    message: str
