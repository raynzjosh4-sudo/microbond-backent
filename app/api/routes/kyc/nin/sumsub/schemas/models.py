from pydantic import BaseModel, Field

class NINSubmissionRequest(BaseModel):
    nin: str = Field(..., description="14-character typed Ugandan NIN")
    first_name: str
    last_name: str
    dob: str = Field(..., description="Format: YYYY-MM-DD")
    is_dependent: bool = Field(default=False)
    document_id: str = Field(..., description="9-digit Card Serial Number")

class NINVerificationData(BaseModel):
    nin: str
    applicant_id: str
    kyc_status: str
    is_dependent: bool

class NINVerificationResponse(BaseModel):
    status: str
    message: str
    data: NINVerificationData
