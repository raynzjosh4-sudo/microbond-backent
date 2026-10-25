from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

class PayoutOrderStrategy(str, Enum):
    ADMIN_ASSIGNED = "Admin Assigned"
    RANDOMIZED = "Randomized by App"
    TRUST_SCORE = "Trust Score Ranked"
    FIRST_COME_FIRST_SERVE = "First Come First Serve"

class RotatingGroupCreateRequest(BaseModel):
    name: str = Field(..., description="Name of the savings group")
    description: str = Field(default="", description="Optional description")
    group_image_url: str = Field(
        default="https://pub-2895dbbc59724eaeb22e030eb9bbdd60.r2.dev/groups/default_rotating.png",
        description="URL of the uploaded group image or Cloudflare R2 URL"
    )
    type: str = Field(..., description="e.g. MERRY_GO_ROUND, GOAL_SAVINGS")
    payment_mode: str = Field(default="OBLIGATION")
    visibility: str = Field(default="PRIVATE")
    currency: str = Field(default="UGX")
    
    # Financials & Timing
    contribution_amount: float = Field(..., description="Exact amount e.g., 10000")
    maximum_member_capacity: Optional[int] = Field(default=None, ge=2, description="Must be a whole number, e.g. 20. Optional for infinite cycles.")
    payouts_per_cycle: int = Field(..., ge=1, description="Members paid per cycle, e.g. 1")
    collection_frequency_days: int = Field(..., ge=0, description="0 means daily at specific time, 7 means weekly, etc.")
    collection_time: Optional[int] = Field(default=None, description="Optional Unix epoch timestamp (ms) for collection time, e.g. 1700000000000")
    group_start_time: int = Field(..., description="Unix epoch timestamp (ms) when the group kicks off, e.g. 1700000000000")
    
    # Strategy & Overrides
    payout_order_strategy: PayoutOrderStrategy = Field(..., description="Must be selected by user")
    admin_assigned_order: Optional[List[int]] = Field(
        default=None, 
        description="Ordered list of user IDs from 1st to last"
    )
    
    # Risk Controls (Must be set)
    minimum_kyc_tier: int = Field(..., ge=0, le=3, description="0: Unverified, 1: Phone, 2: ID, 3: Address")
    require_guarantor: bool = Field(...)
    guarantor_default_action: str = Field(...)
    allow_partial_payments: bool = Field(...)
    allow_advance_deposits: bool = Field(...)
    enforce_payout_holds: bool = Field(...)
    allow_substitute_members: bool = Field(default=False)
    
    # Escrow & Timelocks
    enable_escrow: bool = Field(default=True)
    escrow_release_condition: str = Field(default="Upon unanimous approval")
    enable_timelock: bool = Field(default=True)
    timelock_duration_hours: int = Field(default=24)
    
    # Group Settings (Late Fees & Grace Periods)
    enable_late_fees: bool = Field(default=False)
    late_fee_amount: float = Field(default=0.0, ge=0.0, le=30000.0)
    late_fee_frequency: str = Field(default="DAILY", description="e.g. DAILY, ONCE")
    enable_grace_period: bool = Field(default=False)
    grace_period_hours: int = Field(default=0, description="Grace period in hours")
    
    # Advanced / Admin Settings
    requires_admin_approval: bool = Field(default=False, description="Admin must approve users who join via link")
    missed_payment_action: str = Field(default="STRIKE_AND_KEEP", description="e.g. STRIKE_AND_KEEP, KICK_AND_BAN, USE_GUARANTOR_FUNDS")
    reserve_fund_percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="Percentage going to emergency reserve or admin")
    
    # Settlement & Automation
    auto_disburse_when_full: bool = Field(default=True, description="Automatically disburse payout when all member contributions for the cycle are received")
    multi_sig_payout_approval: bool = Field(default=False, description="Require multi-signature approval from admin and treasurer before disbursement")
    
    # Turn Swaps & Queue Flexibility
    allow_turn_swaps: bool = Field(default=True, description="Allow members to swap payout turns with each other")
    turn_swap_approval_mode: str = Field(default="MUTUAL_CONSENT", description="MUTUAL_CONSENT or ADMIN_APPROVAL_REQUIRED")
    
    # Risk Mitigation (Early-Turn Flight Risk)
    early_turn_security_hold_percentage: float = Field(default=0.0, ge=0.0, le=100.0, description="Percentage held in escrow for early payout turns until cycle completion")
    require_guarantors_for_early_turns_only: bool = Field(default=True, description="Only require guarantors for members taking payouts in the first half of the cycle")
    
    # Renewal & Sequencing
    auto_renew_cycle: bool = Field(default=False, description="Automatically start a new cycle when all rounds complete")
    reverse_payout_order_on_renew: bool = Field(default=True, description="Reverse the payout sequence for the renewed cycle so last becomes first")
    
    # Reminders & Automated Collection
    reminder_lead_time_hours: int = Field(default=24, ge=0, le=168, description="Hours before collection deadline to send reminders")
    enable_auto_debit_prompt: bool = Field(default=True, description="Trigger automatic MoMo USSD prompt at collection time")
