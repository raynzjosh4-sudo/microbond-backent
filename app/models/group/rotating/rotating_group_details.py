from datetime import datetime, time
from decimal import Decimal
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger, DateTime, Numeric, Text, Time
from app.utils.time.now_epoch_ms import now_epoch_ms
from app.utils.time.now_utc_datetime import now_utc_datetime

def utc_now():
    return now_epoch_ms()

class RotatingGroupDetails(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)
    
    contribution_amount: Optional[float] = Field(default=None, description="Per-collection-interval contribution amount (e.g. 5000 UGX daily). Null until explicitly set by admin.")
    payouts_per_cycle: int
    saving_days_per_cycle: Optional[int] = Field(default=None, description="Number of collection intervals per cycle before payout (e.g. 9 days). Null until explicitly set.")
    number_of_cycles: Optional[int] = Field(default=None) # Automatically calculated or None if infinite
    collection_frequency_days: int
    collection_time: Optional[str] = Field(default=None)
    group_start_time: Optional[int] = Field(default=None, sa_column=Column(BigInteger))
    
    payout_order_strategy: str
    is_payout_order_locked: bool = Field(default=False)
    
    # Calculated Rules
    total_expected_pool_per_cycle: Optional[float] = Field(default=None, description="Calculated: contribution_amount * saving_days_per_cycle * member_count")
    
    # Risk Controls
    minimum_kyc_tier: int
    require_guarantor: bool
    guarantor_default_action: str
    allow_partial_payments: bool
    allow_advance_deposits: bool
    
    # Settlement & Automation
    auto_disburse_when_full: bool = Field(default=True, description="Automatically disburse payout when all member contributions for the cycle are received")
    multi_sig_payout_approval: bool = Field(default=False, description="Require multi-signature approval from admin and treasurer before disbursement")
    minimum_partial_payment_amount: Optional[float] = Field(default=None, description="Admin-set minimum amount a member must pay per deposit when partial payments are enabled. If null, defaults to 1,000 UGX.")
    
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
    current_saving_day: int = Field(default=0, description="Tracks the current saving day within the active cycle (0 = not started, 1-N = active)")

    currency_code: str = Field(default="UGX", max_length=3)
    timezone_name: str = Field(default="Africa/Kampala", sa_type=Text)
    collection_start_time: time = Field(default=time(13, 0), sa_type=Time)
    collection_end_time: time = Field(default=time(23, 0), sa_type=Time)
    cycle_length_days: int = Field(default=30, ge=1, le=366)
    recipients_per_cycle: int = Field(default=2, ge=1)
    reserve_percentage: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric, nullable=False),
    )
    reserve_purpose: Optional[str] = Field(default=None, sa_type=Text)
    payout_calculation_mode: str = Field(default="EQUAL_SPLIT", sa_type=Text)
    payout_requires_full_collection: bool = Field(default=True)
    late_payment_grace_minutes: int = Field(default=0, ge=0)
    locked_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=now_utc_datetime,
        sa_type=DateTime(timezone=True),
    )
    created_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
