from typing import Literal, Optional

from pydantic import BaseModel, Field


class UpdateTargetSavingsSettingsRequest(BaseModel):
    allow_max_members: Optional[bool] = None
    max_members: Optional[int] = Field(default=None, ge=2)
    allow_target_amount: Optional[bool] = None
    target_amount: Optional[int] = Field(default=None, gt=0)
    allow_target_date: Optional[bool] = None
    target_date: Optional[int] = Field(default=None, ge=0)
    allow_contribution_schedule: Optional[bool] = None
    contribution_amount: Optional[int] = Field(default=None, ge=0)
    allow_collection_frequency: Optional[bool] = None
    collection_frequency_days: Optional[int] = Field(default=None, ge=0)
    collection_time: Optional[int] = Field(default=None, ge=0)

    allow_multi_payout: Optional[bool] = None
    require_consensus_at_end: Optional[bool] = None
    allow_early_payout_by_vote: Optional[bool] = None
    vote_approval_percentage: Optional[int] = Field(default=None, ge=51, le=100)

    enable_late_fees: Optional[bool] = None
    late_fee_amount: Optional[int] = Field(default=None, ge=0)
    grace_period_hours: Optional[int] = Field(default=None, ge=0)
    missed_payment_action: Optional[Literal["RECORD_STRIKE", "REMOVE_AND_REFUND"]] = None
    minimum_kyc_tier: Optional[int] = Field(default=None, ge=0, le=3)
    hide_leaderboard: Optional[bool] = None

    is_locked: Optional[bool] = None
    lock_funds: Optional[bool] = None
    vis_member_total_savings: Optional[bool] = None
    let_members_view_total_saved: Optional[bool] = None
