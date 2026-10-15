from pydantic import BaseModel, Field

class RingStatus(BaseModel):
    """
    Drives the segmented progress arc around the group's avatar in Jetpack Compose:
    - paid_on_time_count: Green arc
    - missed_deadline_count: Red arc
    - (total - paid - missed): Pending neutral arc
    """
    total_expected_members: int = Field(default=0, ge=0)
    paid_on_time_count: int = Field(default=0, ge=0)
    missed_deadline_count: int = Field(default=0, ge=0)
