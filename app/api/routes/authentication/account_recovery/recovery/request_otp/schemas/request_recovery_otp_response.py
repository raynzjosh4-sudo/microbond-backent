from pydantic import BaseModel


class RequestRecoveryOTPResponse(BaseModel):
    status: str
    message: str
    expires_in_seconds: int
