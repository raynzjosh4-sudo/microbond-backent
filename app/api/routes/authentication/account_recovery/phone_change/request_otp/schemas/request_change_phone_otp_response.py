from pydantic import BaseModel


class RequestChangePhoneOTPResponse(BaseModel):
    status: str
    message: str
    expires_in_seconds: int
