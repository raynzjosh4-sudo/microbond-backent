from pydantic import BaseModel


class VerifyAppPinResponse(BaseModel):
    status: str
    message: str
    valid: bool
