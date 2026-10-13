from pydantic import BaseModel


class VerifyEmailRequest(BaseModel):
    code: str
