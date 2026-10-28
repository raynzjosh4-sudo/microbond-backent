import time
from typing import Literal, Optional

from pydantic import Field, model_validator

from app.schemas.group_creation_request import GroupCreationRequest


class TargetSavingsGroupCreateRequest(GroupCreationRequest):
    name: str = Field(..., min_length=2, max_length=100)
    description: str = Field(default="", max_length=500)
    group_image_url: str
    visibility: str = "PRIVATE"
    currency: str = "UGX"
    allow_max_members: bool = False
    max_members: Optional[int] = Field(default=None, ge=2)

    allow_target_amount: bool = False
    target_amount: Optional[int] = Field(default=None, gt=0)
    allow_target_date: bool = False
    target_date: Optional[int] = Field(default=None, ge=0)
    allow_contribution_schedule: bool = False
    contribution_amount: int = Field(default=0, ge=0)
    allow_collection_frequency: bool = False
    collection_frequency_days: int = Field(default=0, ge=0)
    collection_time: Optional[int] = Field(default=None, ge=0)

    allow_multi_payout: bool = True
    require_consensus_at_end: bool = False
    allow_early_payout_by_vote: bool = False
    vote_approval_percentage: int = Field(default=100, ge=51, le=100)

    enable_late_fees: bool = False
    late_fee_amount: int = Field(default=0, ge=0)
    grace_period_hours: int = Field(default=24, ge=0)
    missed_payment_action: Literal["RECORD_STRIKE", "REMOVE_AND_REFUND"] = "RECORD_STRIKE"
    minimum_kyc_tier: int = Field(default=1, ge=0, le=3)
    hide_leaderboard: bool = False

    @model_validator(mode="after")
    def validate_enabled_settings(self):
        now_ms = int(time.time() * 1000)
        if self.allow_max_members != (self.max_members is not None):
            raise ValueError("Set max_members only when allow_max_members is enabled.")
        if self.allow_target_amount and self.target_amount is None:
            raise ValueError("target_amount is required when allow_target_amount is enabled.")
        if not self.allow_target_amount and self.target_amount is not None:
            raise ValueError("target_amount must be omitted when allow_target_amount is disabled.")
        if self.allow_target_date:
            if self.target_date is None:
                raise ValueError("target_date is required when allow_target_date is enabled.")
            if self.target_date <= now_ms:
                raise ValueError("target_date must be in the future.")
        elif self.target_date is not None:
            raise ValueError("target_date must be omitted when allow_target_date is disabled.")
        if self.allow_contribution_schedule and self.contribution_amount <= 0:
            raise ValueError("contribution_amount must be positive when the schedule is enabled.")
        if not self.allow_contribution_schedule and self.contribution_amount != 0:
            raise ValueError("contribution_amount must be zero when the schedule is disabled.")
        if self.allow_collection_frequency:
            if not self.allow_contribution_schedule:
                raise ValueError("Collection frequency requires a contribution schedule.")
            if self.collection_frequency_days <= 0:
                raise ValueError("collection_frequency_days must be positive when enabled.")
        elif self.collection_frequency_days != 0:
            raise ValueError("collection_frequency_days must be zero when frequency is disabled.")
        if self.enable_late_fees:
            if not self.allow_collection_frequency:
                raise ValueError("Late fees require an enabled contribution frequency.")
            if self.late_fee_amount <= 0:
                raise ValueError("late_fee_amount must be positive when late fees are enabled.")
        elif self.late_fee_amount != 0:
            raise ValueError("late_fee_amount must be zero when late fees are disabled.")

        return self
