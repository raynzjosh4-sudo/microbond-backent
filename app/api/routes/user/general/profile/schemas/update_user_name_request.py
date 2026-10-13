from pydantic import BaseModel, Field


class UpdateUserNameRequest(BaseModel):
    full_name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="New full name, e.g. 'SSENKINDU EMMANUEL'",
    )
