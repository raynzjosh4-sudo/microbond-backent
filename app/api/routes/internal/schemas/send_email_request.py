from pydantic import BaseModel, Field

class SendEmailTaskRequest(BaseModel):
    to_email: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject line")
    html_content: str = Field(..., description="Formatted HTML email body")
