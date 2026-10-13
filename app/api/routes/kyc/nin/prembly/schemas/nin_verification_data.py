from pydantic import BaseModel


class NINVerificationData(BaseModel):
    nin: str
    kyc_status: str
    is_dependent: bool
    verified_name: str
