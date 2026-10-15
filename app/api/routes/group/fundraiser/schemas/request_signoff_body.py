from pydantic import BaseModel, Field

class RequestSignoffBody(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500, description="Why you want to release the funds now.")
