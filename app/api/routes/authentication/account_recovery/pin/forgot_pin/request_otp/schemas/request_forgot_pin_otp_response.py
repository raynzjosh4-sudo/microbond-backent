from pydantic import BaseModel


class RequestForgotPinOTPResponse(BaseModel):
    status: str
    message: str
    expires_in_seconds: int
