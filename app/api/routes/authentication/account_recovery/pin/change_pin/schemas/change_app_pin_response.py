from pydantic import BaseModel


class ChangeAppPinResponse(BaseModel):
    status: str
    message: str
