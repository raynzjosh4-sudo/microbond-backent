from typing import Optional
from pydantic import BaseModel


class KYCDecisionWebhookRequest(BaseModel):
    user_id: str
    decision: str  # "APPROVED" or "REJECTED"
    rejection_reason: Optional[str] = None
    guidance_notes: Optional[str] = None
