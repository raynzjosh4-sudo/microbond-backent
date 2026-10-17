from pydantic import BaseModel, Field


class LogoutResponse(BaseModel):
    status: str = Field(default="success", description="Status code string")
    message: str = Field(description="Informative message regarding the logout action")
    all_devices: bool = Field(default=False, description="Whether all devices were invalidated")
