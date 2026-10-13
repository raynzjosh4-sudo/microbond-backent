from pydantic import BaseModel


class OTPRequest(BaseModel):
    phone_number: str
