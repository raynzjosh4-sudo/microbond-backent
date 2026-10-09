from pydantic import BaseModel, Field

class NINSubmissionRequest(BaseModel):
    nin: str = Field(..., description="14-character typed Ugandan NIN")
    first_name: str
    last_name: str
    dob: str = Field(..., description="Format: YYYY-MM-DD")
    is_dependent: bool = Field(default=False)
