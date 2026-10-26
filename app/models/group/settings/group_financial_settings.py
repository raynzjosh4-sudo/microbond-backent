from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class GroupFinancialSettings(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)
    
    # Payout Rules
    enforce_payout_holds: bool = Field(default=True)
    allow_substitute_members: bool = Field(default=False)
    max_pending_payouts: int = Field(default=2, description="How many payouts can be pending/queued at once")
    
    # Penalties & Grace Period
    enable_late_fees: bool = Field(default=True)
    late_fee_amount: float = Field(default=10000.0)
    late_fee_frequency: str = Field(default="Per day")
    enable_grace_period: bool = Field(default=True)
    grace_period_hours: int = Field(default=24)
    arrears_policy: str = Field(default="Deduct from next payout")
    
    # Payout Limits
    max_payout_active: bool = Field(default=True)
    max_payout_limit: str = Field(default="10,000,000 UGX")
    reserve_fund_percentage: float = Field(default=0.0)
    
    # Escrow & Timelocks
    enable_escrow: bool = Field(default=True)
    escrow_release_condition: str = Field(default="Upon unanimous approval")
    enable_timelock: bool = Field(default=True)
    timelock_duration_hours: int = Field(default=24)
    
    # Fund Stability, Liquidity & Reminders
    liquidity_buffer_percentage: float = Field(default=10.0, description="Percentage of group funds reserved as liquid buffer")
    enable_late_fee_escalation: bool = Field(default=True, description="Escalate late penalty fees each cycle a payment remains missed")
    contribution_reminder_days_before: int = Field(default=2, description="Days before due date to schedule reminder")
    auto_debit_consent_required: bool = Field(default=True, description="Permit automatic collection only from members who opted in")
    emergency_contact_name: Optional[str] = Field(default=None, description="Name of contact for urgent payment issues")
    emergency_contact_phone: Optional[str] = Field(default=None, description="Phone of contact for urgent payment issues")
    enable_sms_call_reminders: bool = Field(default=True, description="Send automated SMS and phone call reminders")
    
    updated_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
