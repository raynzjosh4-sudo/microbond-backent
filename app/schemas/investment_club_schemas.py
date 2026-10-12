from pydantic import BaseModel, Field, model_validator
from typing import Optional


class InvestmentClubGroupCreateRequest(BaseModel):
    # Group identity
    name: str = Field(..., min_length=2, max_length=100, description="Name of the investment club")
    description: str = Field(default="", max_length=500)
    group_image_url: str = Field(..., description="Investment club logo or image URL")
    visibility: str = Field(default="PRIVATE", description="PUBLIC or PRIVATE")
    currency: str = Field(default="UGX")

    # --- InvestmentClubConfig fields (locked at creation) ---
    share_unit_price: int = Field(..., gt=0, description="Cost of a single share in smallest currency units (e.g. 50000 UGX)")
    equity_calculation_mode: str = Field(default="PROPORTIONAL_TO_SHARES", description="PROPORTIONAL_TO_SHARES or FIXED_EQUAL")
    voting_power_logic: str = Field(default="PROPORTIONAL", description="PROPORTIONAL or ONE_MEMBER_ONE_VOTE")
    payout_destination_type: str = Field(default="VERIFIED_BROKERS_ONLY", description="VERIFIED_BROKERS_ONLY or REGISTERED_ASSET_ACCOUNT")
    dividend_distribution_rule: str = Field(default="AUTO_PUSH_PROPORTIONAL", description="AUTO_PUSH_PROPORTIONAL or REINVEST_IN_VAULT")
    lock_in_period_days: int = Field(default=180, ge=0, description="Minimum days member capital is locked")
    liquidation_action: str = Field(default="LIQUIDATE_PROPORTIONAL", description="Action upon dissolution: LIQUIDATE_PROPORTIONAL")

    @model_validator(mode="after")
    def validate_rules(self) -> "InvestmentClubGroupCreateRequest":
        valid_modes = {"PROPORTIONAL_TO_SHARES", "FIXED_EQUAL"}
        if self.equity_calculation_mode not in valid_modes:
            raise ValueError(f"equity_calculation_mode must be one of {valid_modes}")
        valid_voting = {"PROPORTIONAL", "ONE_MEMBER_ONE_VOTE"}
        if self.voting_power_logic not in valid_voting:
            raise ValueError(f"voting_power_logic must be one of {valid_voting}")
        valid_payout = {"VERIFIED_BROKERS_ONLY", "REGISTERED_ASSET_ACCOUNT"}
        if self.payout_destination_type not in valid_payout:
            raise ValueError(f"payout_destination_type must be one of {valid_payout}")
        valid_dividend = {"AUTO_PUSH_PROPORTIONAL", "REINVEST_IN_VAULT"}
        if self.dividend_distribution_rule not in valid_dividend:
            raise ValueError(f"dividend_distribution_rule must be one of {valid_dividend}")
        return self


class UpdateInvestmentClubSettingsRequest(BaseModel):
    minimum_purchase_quota: Optional[int] = Field(default=None, ge=0)
    proposal_approval_threshold_pct: Optional[int] = Field(default=None, ge=51, le=100)
    admin_management_fee_pct: Optional[int] = Field(default=None, ge=0, le=20)
    allow_internal_share_transfers: Optional[bool] = Field(default=None)
    enable_late_fees: Optional[bool] = Field(default=None)

    # Investment Rules & Member Borrowing
    interest_rate_mode: Optional[str] = Field(default=None, description="GROUP_VOTE or FIXED_PERCENTAGE")
    fixed_interest_rate_pct: Optional[float] = Field(default=None)
    require_loan_guarantors: Optional[bool] = Field(default=None)
    min_loan_guarantors: Optional[int] = Field(default=None, ge=0)
    max_borrowing_limit: Optional[int] = Field(default=None, ge=0)
    early_repayment_discount_pct: Optional[float] = Field(default=None, ge=0.0)
    new_share_issuance_mode: Optional[str] = Field(default=None)
    default_recovery_action: Optional[str] = Field(default=None)

    # Fund Stability, Liquidity & Reminders
    contribution_reminder_days_before: Optional[int] = Field(default=None, ge=1)
    auto_debit_consent_required: Optional[bool] = Field(default=None)
    emergency_contact_name: Optional[str] = Field(default=None)
    emergency_contact_phone: Optional[str] = Field(default=None)
    liquidity_buffer_coverage_pct: Optional[int] = Field(default=None, ge=0, le=100)
    enable_late_fee_escalation: Optional[bool] = Field(default=None)
    enable_sms_call_reminders: Optional[bool] = Field(default=None)


class ApplyLoanRequest(BaseModel):
    principal_amount: int = Field(..., gt=0, description="Loan capital requested in smallest currency units")
    due_date: int = Field(..., description="Repayment deadline (epoch ms)")
    purpose: Optional[str] = Field(default=None, max_length=500)


class ReviewLoanRequest(BaseModel):
    status: str = Field(..., description="APPROVED or REJECTED")
    rejection_reason: Optional[str] = Field(default=None)


class RepayLoanRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Amount to repay against loan")



class BuySharesRequest(BaseModel):
    shares_count: int = Field(..., gt=0, description="Number of shares to purchase")


class CreateInvestmentProposalRequest(BaseModel):
    asset_name: str = Field(..., min_length=2, max_length=150, description="Title of the asset (e.g. 5 Acres Maize Farm)")
    asset_type: str = Field(..., description="e.g. AGRICULTURE, REAL_ESTATE, STOCKS, BONDS, MONEY_MARKET")
    required_capital: int = Field(..., gt=0, description="Capital required from the vault")
    expected_roi_pct: Optional[float] = Field(default=None, description="Expected annual or harvest return %")
    description: str = Field(..., min_length=10, max_length=1000, description="Details of the investment thesis")
    broker_destination_account: str = Field(..., description="Registered broker account or mobile money paybill")


class DistributeDividendsRequest(BaseModel):
    total_profit_amount: int = Field(..., gt=0, description="Gross profit amount returned to the club")
    source_asset_name: str = Field(..., min_length=2, max_length=150, description="Name of the asset that yielded the return")
    note: Optional[str] = Field(default=None, max_length=300)


class TransferSharesRequest(BaseModel):
    recipient_user_id: str = Field(..., description="UUID of the active club member receiving the shares")
    shares_count: int = Field(..., gt=0, description="Number of shares to transfer")
