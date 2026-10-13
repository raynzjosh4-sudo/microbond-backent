from pydantic import BaseModel


class VerifyForgotPinOTPResponse(BaseModel):
    status: str
    message: str
    recovery_token: str
    token_type: str = "bearer"
