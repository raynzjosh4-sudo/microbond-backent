from pydantic import BaseModel, Field


class VerifyAppPinRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=8, description="User's App PIN")
