from pydantic import BaseModel, Field

class TransferOwnershipRequest(BaseModel):
    new_owner_user_id: str = Field(..., description="UUID of the active member who will become the new group owner/creator")
