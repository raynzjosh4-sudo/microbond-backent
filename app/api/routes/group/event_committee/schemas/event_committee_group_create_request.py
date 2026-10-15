from pydantic import BaseModel, Field, model_validator
import time

class EventCommitteeGroupCreateRequest(BaseModel):
    # Group identity
    name: str = Field(..., min_length=2, max_length=100, description="Name of the committee or event")
    description: str = Field(default="", max_length=500)
    group_image_url: str = Field(..., description="Event/group profile image URL")
    visibility: str = Field(default="PRIVATE", description="PUBLIC or PRIVATE")
    currency: str = Field(default="UGX")

    # --- EventCommitteeConfig fields (locked at creation) ---
    event_target_budget: int = Field(default=0, ge=0, description="Total estimated event cost. 0 = no fixed target.")
    event_date: int = Field(..., description="When the event happens (epoch ms)")
    collection_deadline: int = Field(..., description="Last date funds must be deposited (epoch ms)")
    payout_destination_type: str = Field(default="VERIFIED_VENDORS_ONLY", description="VERIFIED_VENDORS_ONLY or COMMITTEE_TREASURER")
    spending_signoff_policy: str = Field(default="CHAIRMAN_ONLY", description="CHAIRMAN_ONLY or COMMITTEE_CONSENSUS")
    excess_funds_action: str = Field(default="PROPORTIONAL_REFUND", description="GIFT_TO_BENEFICIARY, PROPORTIONAL_REFUND, ROLLOVER_TO_NEW_EVENT")
    require_invoice_upload: bool = Field(default=True, description="Admin must attach invoice photo before releasing funds")

    @model_validator(mode="after")
    def validate_dates(self) -> "EventCommitteeGroupCreateRequest":
        now_ms = int(time.time() * 1000)
        if self.event_date <= now_ms:
            raise ValueError("event_date must be in the future.")
        if self.collection_deadline <= now_ms:
            raise ValueError("collection_deadline must be in the future.")
        if self.collection_deadline > self.event_date:
            raise ValueError("collection_deadline must be before or on the event_date.")
        valid_excess = {"GIFT_TO_BENEFICIARY", "PROPORTIONAL_REFUND", "ROLLOVER_TO_NEW_EVENT"}
        if self.excess_funds_action not in valid_excess:
            raise ValueError(f"excess_funds_action must be one of {valid_excess}")
        return self
