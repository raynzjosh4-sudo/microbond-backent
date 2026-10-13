from pydantic import BaseModel, EmailStr


class LinkEmailRequest(BaseModel):
    email: EmailStr
