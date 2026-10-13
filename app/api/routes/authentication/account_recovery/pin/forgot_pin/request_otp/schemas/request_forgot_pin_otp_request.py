from pydantic import BaseModel


class RequestForgotPinOTPRequest(BaseModel):
    phone_number: str
