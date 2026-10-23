import json
from app.services.fee_engines.welfare_fund.schemas.emergency_deposit_calculation import (
    EmergencyDepositCalculation,
    TARGET_PAYOUT_FEE,
)
from app.core.microbond_core import calculate_emergency_deposit_fee as core_calculate_emergency_fee


def calculate_emergency_group_deposit(
    deposit_amount: int,
    group_pending_payout_fees_count: int,
) -> EmergencyDepositCalculation:
    """
    Calculate the exact MTN RequestToPay charge for a routine welfare deposit
    using the authoritative microbond_core domain engine.
    """
    if not isinstance(deposit_amount, int) or deposit_amount <= 0:
        raise ValueError(f"deposit_amount must be a positive int. Got: {deposit_amount!r}")
    if not isinstance(group_pending_payout_fees_count, int) or group_pending_payout_fees_count < 0:
        raise ValueError(
            f"group_pending_payout_fees_count must be a non-negative int. "
            f"Got: {group_pending_payout_fees_count!r}"
        )

    raw = core_calculate_emergency_fee(
        deposit_amount=deposit_amount,
        group_pending_payout_fees_count=group_pending_payout_fees_count,
        target_payout_fee=TARGET_PAYOUT_FEE,
    )
    res = json.loads(raw)

    return EmergencyDepositCalculation(
        deposit_amount=res["deposit_amount"],
        base_charge_amount=res["base_charge_amount"],
        mtn_deposit_fee=res["mtn_deposit_fee"],
        microbond_deposit_fee=res["microbond_deposit_fee"],
        hidden_payout_fee=res["hidden_payout_fee"],
        final_charge_amount=res["final_charge_amount"],
        cleared_pending_fee=res["cleared_pending_fee"],
        fees_cleared=res["fees_cleared"],
    )

