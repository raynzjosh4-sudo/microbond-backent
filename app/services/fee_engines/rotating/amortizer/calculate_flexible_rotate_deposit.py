import json
from app.services.fee_engines.base_deposit_fee import calculate_deposit_fee, DepositFeeBreakdown
from app.services.fee_engines.rotating.amortizer.schemas.member_deposit_schedule import (
    TARGET_PAYOUT_FEE,
)
from app.services.fee_engines.rotating.amortizer.schemas.flexible_rotate_deposit_result import (
    FlexibleRotateDepositResult,
)
from app.core.microbond_core import calculate_flexible_rotate_deposit as core_calculate_flexible_deposit


def calculate_flexible_rotate_deposit(
    deposit_amount: int,
    current_saved_amount: int,
    assigned_value_milestone: int,
    fee_already_collected: bool,
) -> FlexibleRotateDepositResult:
    """
    Calculate the exact MTN RequestToPay charge for a rotating group deposit,
    supporting lump-sum advance payments and catch-up arrears payments using microbond_core.
    """
    if not isinstance(deposit_amount, int) or deposit_amount <= 0:
        raise ValueError(f"deposit_amount must be a positive int. Got: {deposit_amount!r}")
    if not isinstance(assigned_value_milestone, int) or assigned_value_milestone <= 0:
        raise ValueError(f"assigned_value_milestone must be a positive int. Got: {assigned_value_milestone!r}")

    base: DepositFeeBreakdown = calculate_deposit_fee(deposit_amount)

    raw = core_calculate_flexible_deposit(
        deposit_amount=deposit_amount,
        current_saved_amount=current_saved_amount,
        assigned_value_milestone=assigned_value_milestone,
        fee_already_collected=fee_already_collected,
        target_payout_fee=TARGET_PAYOUT_FEE,
        mtn_flat_fee=base.mtn_fee,
        platform_fee_bps=int((base.platform_fee * 10_000) // max(1, deposit_amount)),
    )
    res = json.loads(raw)

    return FlexibleRotateDepositResult(
        deposit_amount=res["deposit_amount"],
        base_charge_amount=base.charge_amount,
        mtn_deposit_fee=base.mtn_fee,
        microbond_base_fee=base.platform_fee,
        hidden_payout_fee=res["hidden_payout_fee"],
        final_charge_amount=base.charge_amount + res["hidden_payout_fee"],
        milestone_triggered_now=res["milestone_triggered_now"],
        new_cumulative_total=res["new_cumulative_total"],
        assigned_value_milestone=res["assigned_value_milestone"],
    )
