from app.services.fee_engines.base_deposit_fee import calculate_deposit_fee, DepositFeeBreakdown
from app.services.fee_engines.welfare_fund.schemas.emergency_deposit_calculation import (
    EmergencyDepositCalculation,
    TARGET_PAYOUT_FEE,
)


def calculate_emergency_group_deposit(
    deposit_amount: int,
    group_pending_payout_fees_count: int,
) -> EmergencyDepositCalculation:
    """
    Calculate the exact MTN RequestToPay charge for a routine welfare deposit.

    If the group has any pending payout fees queued from recent emergency
    disbursements, this deposit silently absorbs ALL of them in a single
    charge. The queue is cleared in full — not one at a time — to avoid
    spreading micro-additions across multiple future depositors.
    """
    if not isinstance(deposit_amount, int) or deposit_amount <= 0:
        raise ValueError(f"deposit_amount must be a positive int. Got: {deposit_amount!r}")
    if not isinstance(group_pending_payout_fees_count, int) or group_pending_payout_fees_count < 0:
        raise ValueError(
            f"group_pending_payout_fees_count must be a non-negative int. "
            f"Got: {group_pending_payout_fees_count!r}"
        )

    base: DepositFeeBreakdown = calculate_deposit_fee(deposit_amount)

    fees_to_clear: int = group_pending_payout_fees_count
    total_payout_fee: int = fees_to_clear * TARGET_PAYOUT_FEE
    final_charge: int = base.charge_amount + total_payout_fee

    return EmergencyDepositCalculation(
        deposit_amount=deposit_amount,
        base_charge_amount=base.charge_amount,
        mtn_deposit_fee=base.mtn_fee,
        microbond_deposit_fee=base.platform_fee,
        hidden_payout_fee=total_payout_fee,
        final_charge_amount=final_charge,
        cleared_pending_fee=fees_to_clear > 0,
        fees_cleared=fees_to_clear,
    )
