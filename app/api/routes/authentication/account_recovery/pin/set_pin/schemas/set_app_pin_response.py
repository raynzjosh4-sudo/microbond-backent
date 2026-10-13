from pydantic import BaseModel


class SetAppPinResponse(BaseModel):
    status: str
    message: str
    access_token: str
    token_type: str = "bearer"
