from typing import Optional
from pydantic import BaseModel, Field, field_validator


class OTPVerifyRequest(BaseModel):
    phone_number: str = Field(min_length=7, max_length=20)
    code: str = Field(min_length=6, max_length=6)
    device_id: Optional[str] = None

    @field_validator("code")
    @classmethod
    def code_must_be_digits(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized.isdigit():
            raise ValueError("OTP must contain six digits")
        return normalized


OTPVerify = OTPVerifyRequest
