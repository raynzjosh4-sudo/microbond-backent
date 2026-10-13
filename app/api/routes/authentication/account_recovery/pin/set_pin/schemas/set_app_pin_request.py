from pydantic import BaseModel


class SetAppPinRequest(BaseModel):
    pin: str
