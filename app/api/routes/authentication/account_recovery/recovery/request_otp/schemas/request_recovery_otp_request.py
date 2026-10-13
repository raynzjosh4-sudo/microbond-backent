from pydantic import BaseModel


class RequestRecoveryOTPRequest(BaseModel):
    old_phone_number: str
    app_pin: str
    new_phone_number: str
