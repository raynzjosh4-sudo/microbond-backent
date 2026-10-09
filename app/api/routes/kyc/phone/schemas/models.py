from pydantic import BaseModel

class ForceKYCRequest(BaseModel):
    phone_number: str
