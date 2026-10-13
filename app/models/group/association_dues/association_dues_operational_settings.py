from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class AssociationDuesOperationalSettings(SQLModel, table=True):
    """
    Admin-managed settings + live collection and defaulters tracker.
    """
    __tablename__ = "associationduesoperationalsettings"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)

    auto_sweep_trigger: str = Field(default="END_OF_CYCLE", description="INSTANT, END_OF_CYCLE, or MANUAL_WITHDRAWAL")
    allow_advance_payments: bool = Field(default=True, description="Allow members to pre-pay multiple cycles ahead")
    allow_installments: bool = Field(default=True, description="Allow members to pay dues in installments / partial amounts")
    grace_period_days: int = Field(default=7, description="Days after due date before marked In Arrears")
    late_fee_amount: int = Field(default=0, sa_column=Column(BigInteger), description="Flat penalty added to dues balance")
    arrears_action: str = Field(default="SUSPEND_MEMBERSHIP", description="SUSPEND_MEMBERSHIP or EXPEL_AFTER_LIMIT")
    max_missed_cycles_allowed: int = Field(default=3, description="Consecutive missed cycles before expulsion")
    show_defaulters_publicly: bool = Field(default=False, description="Display defaulters list on dashboard")
    treasury_ledger_visibility: str = Field(default="TRANSPARENT", description="TRANSPARENT or ADMIN_ONLY")

    # Arrears Policy & Reminders
    send_arrears_reminders: bool = Field(default=True, description="Send notifications to members with overdue dues")
    arrears_reminder_days_before: int = Field(default=3, description="Days before due date or overdue to remind")
    restrict_voting_on_arrears: bool = Field(default=True, description="Disable voting rights when in arrears")
    restrict_welfare_claims_on_arrears: bool = Field(default=True, description="Disable welfare/benefit claims when in arrears")

    # Live counters
    current_balance: int = Field(default=0, sa_column=Column(BigInteger), description="Live dues in vault awaiting sweep")
    total_collected: int = Field(default=0, sa_column=Column(BigInteger), description="Cumulative dues collected")
    total_swept_to_treasury: int = Field(default=0, sa_column=Column(BigInteger), description="Cumulative funds pushed to association account")
    active_defaulters_count: int = Field(default=0, description="Current number of members in arrears")
    is_active: bool = Field(default=True)

    updated_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
