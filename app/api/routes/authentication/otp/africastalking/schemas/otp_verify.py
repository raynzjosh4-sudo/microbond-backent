from typing import Optional
from pydantic import BaseModel


class OTPVerify(BaseModel):
    phone_number: str
    code: str
    device_id: Optional[str] = None
