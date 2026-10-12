from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
from datetime import datetime, timezone
import uuid


def utc_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


# ---------------------------------------------------------------------------
# INVESTMENT CLUB GROUP — Tables
# ---------------------------------------------------------------------------

class InvestmentClubConfig(SQLModel, table=True):
    """
    Set ONCE at group creation. Constitutional equity & voting rules.
    """
    __tablename__ = "investmentclubconfig"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)

    share_unit_price: int = Field(sa_column=Column(BigInteger), description="Cost of one equity share in smallest currency unit")
    equity_calculation_mode: str = Field(default="PROPORTIONAL_TO_SHARES", description="PROPORTIONAL_TO_SHARES or FIXED_EQUAL")
    voting_power_logic: str = Field(default="PROPORTIONAL", description="PROPORTIONAL or ONE_MEMBER_ONE_VOTE")
    payout_destination_type: str = Field(default="VERIFIED_BROKERS_ONLY", description="VERIFIED_BROKERS_ONLY or REGISTERED_ASSET_ACCOUNT")
    dividend_distribution_rule: str = Field(default="AUTO_PUSH_PROPORTIONAL", description="AUTO_PUSH_PROPORTIONAL or REINVEST_IN_VAULT")
    lock_in_period_days: int = Field(default=180, description="Minimum days member capital is locked before withdrawal")
    liquidation_action: str = Field(default="LIQUIDATE_PROPORTIONAL", description="Action upon dissolution: LIQUIDATE_PROPORTIONAL")

    created_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))


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

    updated_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))


class InvestmentClubLoan(SQLModel, table=True):
    """
    Tracks internal credit facility loans taken by members against their equity stake.
    """
    __tablename__ = "investmentclubloan"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)

    principal_amount: int = Field(sa_column=Column(BigInteger), description="Loan capital requested in smallest currency unit")
    interest_rate_pct: float = Field(default=10.0, description="Interest rate agreed at approval")
    total_due_amount: int = Field(sa_column=Column(BigInteger), description="Principal + interest due")
    amount_repaid: int = Field(default=0, sa_column=Column(BigInteger), description="Total amount repaid to date")
    early_discount_applied: int = Field(default=0, sa_column=Column(BigInteger))

    status: str = Field(default="PENDING", description="PENDING, APPROVED, DISBURSED, REPAID, DEFAULTED, REJECTED")
    guarantors_count: int = Field(default=0)
    due_date: int = Field(sa_column=Column(BigInteger), description="Repayment deadline (epoch ms)")
    disbursed_at: Optional[int] = Field(default=None, sa_column=Column(BigInteger))
    settled_at: Optional[int] = Field(default=None, sa_column=Column(BigInteger))

    approved_by: Optional[uuid.UUID] = Field(default=None, foreign_key="user.id")
    created_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))
    updated_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))



class InvestmentClubMemberShare(SQLModel, table=True):
    """
    Tracks individual member equity shares and capital invested in the club.
    """
    __tablename__ = "investmentclubmembershare"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)

    shares_owned: int = Field(default=0, description="Number of shares held")
    total_invested: int = Field(default=0, sa_column=Column(BigInteger), description="Total amount paid for shares")
    last_dividend_received: int = Field(default=0, sa_column=Column(BigInteger))

    created_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))
    updated_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))


# ---------------------------------------------------------------------------
# ASSOCIATION DUES GROUP — Tables
# ---------------------------------------------------------------------------

class AssociationDuesConfig(SQLModel, table=True):
    """
    Set ONCE at group creation. Defines subscription dues rules & treasury routing.
    """
    __tablename__ = "associationduesconfig"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)

    dues_amount: int = Field(sa_column=Column(BigInteger), description="Mandatory recurring subscription fee")
    billing_cycle_days: int = Field(default=30, description="Cycle interval: 30=Monthly, 90=Quarterly, 365=Annually")
    billing_start_date: int = Field(sa_column=Column(BigInteger), description="When first cycle officially commences (epoch ms)")
    treasury_account_id: str = Field(description="UUID of verified Bank or MoMo account belonging to Association")
    enable_prorated_dues: bool = Field(default=True, description="Prorate dues for members joining mid-cycle")

    created_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))


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

    updated_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))


class AssociationMemberDuesStanding(SQLModel, table=True):
    """
    Tracks individual member subscription cycles, payment status, and arrears.
    """
    __tablename__ = "associationmemberduesstanding"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)

    cycles_paid_ahead: int = Field(default=0, description="Number of future cycles prepaid")
    consecutive_missed_cycles: int = Field(default=0, description="Consecutive unpaid cycles")
    outstanding_arrears_balance: int = Field(default=0, sa_column=Column(BigInteger), description="Total unpaid dues and late fees")
    is_in_arrears: bool = Field(default=False)
    is_suspended: bool = Field(default=False)
    last_payment_date: Optional[int] = Field(default=None, sa_column=Column(BigInteger))
    next_due_date: int = Field(sa_column=Column(BigInteger))

    updated_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))


class AssociationDuesExemption(SQLModel, table=True):
    """
    Manages temporary or permanent dues exemptions for association members
    (e.g. students, hardship, elders, honorary members).
    """
    __tablename__ = "associationduesexemption"

    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)

    exemption_type: str = Field(default="TEMPORARY", description="TEMPORARY or PERMANENT")
    reason: str = Field(default="HARDSHIP", description="HARDSHIP, STUDENT, ELDER, HONORARY, SICKNESS, or OTHER")
    notes: Optional[str] = Field(default=None, description="Admin notes or justifications for exemption")
    discount_percentage: int = Field(default=100, description="Percentage of dues waived (100 = full exemption)")

    start_date: int = Field(sa_column=Column(BigInteger), description="Epoch ms when exemption starts")
    end_date: Optional[int] = Field(default=None, sa_column=Column(BigInteger), description="Epoch ms when exemption ends (None for PERMANENT)")
    is_active: bool = Field(default=True)
    approved_by: Optional[uuid.UUID] = Field(default=None, foreign_key="user.id")

    created_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))
    updated_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))

