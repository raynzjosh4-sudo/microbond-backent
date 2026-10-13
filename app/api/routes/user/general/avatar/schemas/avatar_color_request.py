from pydantic import BaseModel


class AvatarColorRequest(BaseModel):
    color: str
