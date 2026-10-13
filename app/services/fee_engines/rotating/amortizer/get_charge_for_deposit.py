from app.services.fee_engines.base_deposit_fee import calculate_deposit_fee, DepositFeeBreakdown
from app.services.fee_engines.rotating.amortizer.schemas.member_deposit_schedule import (
    TARGET_PAYOUT_FEE,
)


def get_charge_for_deposit(
    group_target_amount: int,
    member_milestone_round: int,
    current_round_number: int,
) -> int:
    """
    Lightweight helper for the deposit pipeline: given a member's pre-stored
    milestone round and the current round, return the exact charge amount to
    send to MTN RequestToPay.
    """
    base: DepositFeeBreakdown = calculate_deposit_fee(group_target_amount)
    if current_round_number == member_milestone_round:
        return base.charge_amount + TARGET_PAYOUT_FEE
    return base.charge_amount
