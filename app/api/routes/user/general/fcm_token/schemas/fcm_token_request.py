from typing import Optional
from pydantic import BaseModel, Field


class FCMTokenRequest(BaseModel):
    token: str = Field(
        ...,
        min_length=10,
        description="FCM device registration token from Firebase SDK (obtained via FirebaseMessaging.getInstance().getToken())",
    )
    platform: Optional[str] = Field(
        default="ANDROID", description="Client platform: ANDROID | IOS"
    )
