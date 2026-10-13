from pydantic import BaseModel


class VerifyForgotPinOTPRequest(BaseModel):
    phone_number: str
    code: str
