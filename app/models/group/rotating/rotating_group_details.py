from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class RotatingGroupDetails(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)
    
    contribution_amount: float
    payouts_per_cycle: int
    number_of_cycles: Optional[int] = Field(default=None) # Automatically calculated or None if infinite
    collection_frequency_days: int
    collection_time: Optional[str] = Field(default=None)
    group_start_time: int = Field(sa_column=Column(BigInteger))
    
    payout_order_strategy: str
    is_payout_order_locked: bool = Field(default=False)
    
    # Calculated Rules
    total_expected_pool_per_cycle: float
    
    # Risk Controls
    minimum_kyc_tier: int
    require_guarantor: bool
    guarantor_default_action: str
    allow_partial_payments: bool
    allow_advance_deposits: bool
    
    # Settlement & Automation
    auto_disburse_when_full: bool = Field(default=True, description="Automatically disburse payout when all member contributions for the cycle are received")
    multi_sig_payout_approval: bool = Field(default=False, description="Require multi-signature approval from admin and treasurer before disbursement")
    
    # Turn Swaps & Queue Flexibility
    allow_turn_swaps: bool = Field(default=True, description="Allow members to swap payout turns with each other")
    turn_swap_approval_mode: str = Field(default="MUTUAL_CONSENT", description="MUTUAL_CONSENT or ADMIN_APPROVAL_REQUIRED")
    
    # Risk Mitigation (Early-Turn Flight Risk)
    early_turn_security_hold_percentage: float = Field(default=0.0, description="Percentage held in escrow for early payout turns until cycle completion")
    require_guarantors_for_early_turns_only: bool = Field(default=True, description="Only require guarantors for members taking payouts in the first half of the cycle")
    
    # Renewal & Sequencing
    auto_renew_cycle: bool = Field(default=False, description="Automatically start a new cycle when all rounds complete")
    reverse_payout_order_on_renew: bool = Field(default=True, description="Reverse the payout sequence for the renewed cycle so last becomes first")
    
    # Reminders & Automated Collection
    reminder_lead_time_hours: int = Field(default=24, description="Hours before collection deadline to send reminders")
    enable_auto_debit_prompt: bool = Field(default=True, description="Trigger automatic MoMo USSD prompt at collection time")
    
    current_cycle: int = Field(default=1)
    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
