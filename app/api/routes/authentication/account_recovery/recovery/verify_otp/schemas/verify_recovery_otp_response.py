from pydantic import BaseModel


class VerifyRecoveryOTPResponse(BaseModel):
    status: str
    message: str
    temp_recovery_token: str
