from pydantic import BaseModel


class ChangeAppPinRequest(BaseModel):
    old_pin: str
    new_pin: str
