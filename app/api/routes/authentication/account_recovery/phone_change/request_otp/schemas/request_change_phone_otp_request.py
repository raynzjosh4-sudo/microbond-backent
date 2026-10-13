from pydantic import BaseModel


class RequestChangePhoneOTPRequest(BaseModel):
    new_phone_number: str
