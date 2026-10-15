from typing import Optional, Dict
from pydantic import BaseModel, Field

class SendPushTaskRequest(BaseModel):
    token: str = Field(..., description="Firebase FCM device token")
    title: str = Field(..., description="Push notification title")
    body: str = Field(..., description="Push notification body text")
    data: Optional[Dict[str, str]] = Field(default=None, description="Optional metadata payload")
