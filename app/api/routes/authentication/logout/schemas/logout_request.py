from pydantic import BaseModel, Field


class LogoutRequest(BaseModel):
    all_devices: bool = Field(
        default=False,
        description="If True, revokes all active sessions for this user across all devices.",
    )
