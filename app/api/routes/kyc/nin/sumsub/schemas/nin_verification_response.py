from pydantic import BaseModel
from .nin_verification_data import NINVerificationData


class NINVerificationResponse(BaseModel):
    status: str
    message: str
    data: NINVerificationData
