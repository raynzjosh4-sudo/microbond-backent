from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
import uuid
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class InvestmentClubOperationalSettings(SQLModel, table=True):
    """
    Admin-managed settings + live asset & share counters.
    """
    __tablename__ = "investmentcluboperationalsettings"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)

    minimum_purchase_quota: int = Field(default=0, description="Min shares a member must buy each cycle to stay in good standing")
    proposal_approval_threshold_pct: int = Field(default=66, description="% votes required to approve funding an asset (51-100)")
    admin_management_fee_pct: int = Field(default=0, description="% cut of profits to admin for managing assets (0-20)")
    allow_internal_share_transfers: bool = Field(default=True, description="Allow members to trade shares peer-to-peer inside the app")
    enable_late_fees: bool = Field(default=False)

    # Investment Rules & Member Borrowing (Internal Credit Facility)
    interest_rate_mode: str = Field(default="GROUP_VOTE", description="GROUP_VOTE or FIXED_PERCENTAGE")
    fixed_interest_rate_pct: float = Field(default=10.0, description="Annual/monthly borrowing interest rate if fixed")
    require_loan_guarantors: bool = Field(default=True, description="Require fellow members to co-sign / guarantee loans")
    min_loan_guarantors: int = Field(default=2, description="Minimum number of guarantors required per loan application")
    max_borrowing_limit: int = Field(default=2000000, sa_column=Column(BigInteger), description="Maximum credit limit a single member can borrow")
    early_repayment_discount_pct: float = Field(default=2.0, description="Interest discount for clearing loan ahead of schedule")
    new_share_issuance_mode: str = Field(default="MEMBER_APPROVAL", description="MEMBER_APPROVAL or ADMIN_DISCRETION")
    default_recovery_action: str = Field(default="COLLATERAL_SEIZURE", description="COLLATERAL_SEIZURE, GUARANTOR_DEDUCTION, or EXPULSION")

    # Fund Stability, Liquidity & Reminders
    contribution_reminder_days_before: int = Field(default=2, description="Days before due date to schedule reminder")
    auto_debit_consent_required: bool = Field(default=True, description="Permit automatic collection only from members who opted in")
    emergency_contact_name: Optional[str] = Field(default=None, description="Contact name for urgent payment issues")
    emergency_contact_phone: Optional[str] = Field(default=None, description="Contact phone for urgent payment issues")
    liquidity_buffer_coverage_pct: int = Field(default=10, description="Percentage of club assets reserved as liquid buffer (0-100)")
    enable_late_fee_escalation: bool = Field(default=True, description="Escalate late penalty fees each cycle a payment remains missed")
    enable_sms_call_reminders: bool = Field(default=True, description="Send automated SMS and phone call reminders to admins/members")

    # Live counters
    current_balance: int = Field(default=0, sa_column=Column(BigInteger), description="Uninvested cash in vault")
    total_invested_capital: int = Field(default=0, sa_column=Column(BigInteger), description="Capital currently deployed in active assets")
    total_shares_issued: int = Field(default=0, sa_column=Column(BigInteger), description="Total equity shares held by members")
    total_dividends_distributed: int = Field(default=0, sa_column=Column(BigInteger), description="Cumulative dividends paid out")
    active_loans_count: int = Field(default=0, description="Current number of active member loans")
    total_loans_disbursed: int = Field(default=0, sa_column=Column(BigInteger), description="Cumulative loan capital disbursed")
    is_active: bool = Field(default=True)

    updated_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
