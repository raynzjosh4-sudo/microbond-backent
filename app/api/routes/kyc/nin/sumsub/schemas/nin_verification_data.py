from pydantic import BaseModel


class NINVerificationData(BaseModel):
    nin: str
    applicant_id: str
    kyc_status: str
    is_dependent: bool
