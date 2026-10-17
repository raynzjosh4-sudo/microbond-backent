from pydantic import BaseModel, EmailStr


class RequestEmailRecoveryCodeRequest(BaseModel):
    email: EmailStr


class RequestEmailRecoveryCodeResponse(BaseModel):
    status: str
    message: str
    expires_in_seconds: int = 900


class VerifyEmailRecoveryCodeRequest(BaseModel):
    email: EmailStr
    code: str


class VerifyEmailRecoveryCodeResponse(BaseModel):
    status: str
    message: str
    temp_recovery_token: str


class RequestRecoveryPhoneOTPRequest(BaseModel):
    new_phone_number: str


class RequestRecoveryPhoneOTPResponse(BaseModel):
    status: str
    message: str
    expires_in_seconds: int = 300


class ConfirmRecoveryPhoneOTPRequest(BaseModel):
    new_phone_number: str
    code: str


class ConfirmRecoveryPhoneOTPResponse(BaseModel):
    status: str
    message: str
    recovery_token: str
