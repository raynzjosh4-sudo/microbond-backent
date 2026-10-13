from dataclasses import dataclass
from app.services.fee_engines.rotating.surplus.schemas.withdrawal_eligibility_status import (
    WithdrawalEligibilityStatus,
)


@dataclass(frozen=True)
class SurplusWithdrawalEvaluation:
    """
    Security and liquidity validation for accidental overpayment refunds.
    """
    status: WithdrawalEligibilityStatus
    is_eligible: bool
    requested_amount_ugx: int
    approved_gross_amount_ugx: int
    telecom_disbursement_fee_ugx: int
    net_payout_to_member_ugx: int
    remaining_credit_after_refund: int
    group_pool_balance_after_refund: int
    reason_message: str
