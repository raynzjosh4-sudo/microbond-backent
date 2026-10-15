from pydantic import BaseModel, Field
from typing import Optional

class TargetSavingsGroupCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Name of the savings group")
    description: str = Field(default="", max_length=500, description="Optional description")
    group_image_url: str = Field(..., description="URL of the uploaded group image")
    type: str = Field(default="GOAL_SAVINGS", description="Group type")
    payment_mode: str = Field(default="OBLIGATION")
    visibility: str = Field(default="PRIVATE")
    currency: str = Field(default="UGX")
    
    # 1. Savings Goal & Schedule (Whole Numbers Only)
    target_date: int = Field(..., description="Target end date as a Unix timestamp in milliseconds")
    target_amount: int = Field(default=0, ge=0, description="Total monetary goal in whole currency (UGX). 0 means save until date.")
    contribution_amount: int = Field(default=0, ge=0, description="Amount each member must save per cycle. 0 means flexible.")
    collection_frequency_days: int = Field(default=0, ge=0, description="0=Flexible/Daily, 7=Weekly, 14=Bi-weekly, 30=Monthly")
    collection_time: Optional[int] = Field(default=None, description="Optional cutoff time of day in milliseconds")
    
    # 2. Where the Money Goes at the End
    payout_destination_type: str = Field(
        default="PROPORTIONAL_RETURN", 
        description="PROPORTIONAL_RETURN (back to each member) or SINGLE_NOMINATED_ACCOUNT (for group project/purchase)"
    )
    nominated_account_id: Optional[str] = Field(
        default=None, 
        description="UUID of verified payment destination if SINGLE_NOMINATED_ACCOUNT is selected"
    )
    
    # 3. Group Agreement & Voting Rules
    require_consensus_at_end: bool = Field(default=False, description="Require members to vote to release money at the target date")
    allow_early_payout_by_vote: bool = Field(default=True, description="Allow members to vote to end savings early")
    vote_approval_percentage: int = Field(default=100, ge=51, le=100, description="Percentage of members who must agree (51-100%)")
    
    # 4. Late Fees & Rules
    enable_late_fees: bool = Field(default=False, description="Charge a small fee if a member pays late")
    late_fee_amount: int = Field(default=0, ge=0, description="Flat late fee in whole currency units")
    grace_period_hours: int = Field(default=24, ge=0, description="Hours of grace before late fee applies")
    missed_payment_action: str = Field(default="RECORD_STRIKE", description="RECORD_STRIKE or REMOVE_AND_REFUND")
    minimum_kyc_tier: int = Field(default=1, ge=0, le=3, description="Minimum verification tier required to join (0-3)")
    hide_leaderboard: bool = Field(default=False, description="Hide member contribution rankings")
