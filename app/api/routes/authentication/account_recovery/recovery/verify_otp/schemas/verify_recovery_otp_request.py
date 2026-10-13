from pydantic import BaseModel


class VerifyRecoveryOTPRequest(BaseModel):
    phone_number: str
    code: str
