from pydantic import BaseModel, Field


class GroupCreationRequest(BaseModel):
    start_date: int = Field(
        ...,
        ge=0,
        description="Unix timestamp in milliseconds when the group becomes active.",
    )
    minimum_kyc_tier: int = Field(
        default=1,
        ge=0,
        le=3,
        description="Minimum KYC tier required for members to join the group.",
    )
