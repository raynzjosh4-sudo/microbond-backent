from pydantic import BaseModel


class OTPRequestResponse(BaseModel):
    status: str
    message: str
    expires_in_seconds: int
