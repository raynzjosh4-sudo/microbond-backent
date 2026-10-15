from typing import Optional
from pydantic import BaseModel, Field

class UpdateTargetSavingsSettingsRequest(BaseModel):
    contribution_amount: Optional[int] = Field(default=None, ge=0, description="Amount each member must save per cycle")
    collection_frequency_days: Optional[int] = Field(default=None, ge=0, description="0=Flexible/Daily, 7=Weekly, 14=Bi-weekly, 30=Monthly")
    collection_time: Optional[int] = Field(default=None, description="Cutoff time of day in milliseconds")
    
    # Consensus & Voting Rules
    require_consensus_at_end: Optional[bool] = Field(default=None, description="Require members to vote to release money at the target date")
    allow_early_payout_by_vote: Optional[bool] = Field(default=None, description="Allow members to vote to end savings early")
    vote_approval_percentage: Optional[int] = Field(default=None, ge=51, le=100, description="Percentage of members who must agree (51-100%)")
    
    # Late Fees & Rules
    enable_late_fees: Optional[bool] = Field(default=None, description="Charge a small fee if a member pays late")
    late_fee_amount: Optional[int] = Field(default=None, ge=0, description="Flat late fee in whole currency units")
    grace_period_hours: Optional[int] = Field(default=None, ge=0, description="Hours of grace before late fee applies")
    missed_payment_action: Optional[str] = Field(default=None, description="RECORD_STRIKE or REMOVE_AND_REFUND")
    minimum_kyc_tier: Optional[int] = Field(default=None, ge=0, le=3, description="Minimum verification tier required to join (0-3)")
    hide_leaderboard: Optional[bool] = Field(default=None, description="Hide member contribution rankings")
