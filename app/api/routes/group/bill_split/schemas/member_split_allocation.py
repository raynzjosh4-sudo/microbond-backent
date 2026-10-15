import uuid
from pydantic import BaseModel, Field

class MemberSplitAllocation(BaseModel):
    user_id: uuid.UUID
    assigned_amount: int = Field(..., gt=0, description="Amount assigned to this member in smallest currency unit")
