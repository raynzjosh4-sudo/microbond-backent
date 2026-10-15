from pydantic import BaseModel, Field

class SendSMSTaskRequest(BaseModel):
    phone_number: str = Field(..., description="Recipient phone number (Ugandan MSISDN)")
    message: str = Field(..., min_length=1, max_length=500, description="SMS text content")
