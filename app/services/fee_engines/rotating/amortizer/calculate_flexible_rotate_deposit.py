from app.services.fee_engines.base_deposit_fee import calculate_deposit_fee, DepositFeeBreakdown
from app.services.fee_engines.rotating.amortizer.schemas.member_deposit_schedule import (
    TARGET_PAYOUT_FEE,
)
from app.services.fee_engines.rotating.amortizer.schemas.flexible_rotate_deposit_result import (
    FlexibleRotateDepositResult,
)


def calculate_flexible_rotate_deposit(
    deposit_amount: int,
    current_saved_amount: int,
    assigned_value_milestone: int,
    fee_already_collected: bool,
) -> FlexibleRotateDepositResult:
    """
    Calculate the exact MTN RequestToPay charge for a rotating group deposit,
    supporting lump-sum advance payments and catch-up arrears payments.
    """
    if not isinstance(deposit_amount, int) or deposit_amount <= 0:
        raise ValueError(f"deposit_amount must be a positive int. Got: {deposit_amount!r}")
    if not isinstance(assigned_value_milestone, int) or assigned_value_milestone <= 0:
        raise ValueError(f"assigned_value_milestone must be a positive int. Got: {assigned_value_milestone!r}")

    base: DepositFeeBreakdown = calculate_deposit_fee(deposit_amount)

    new_cumulative = current_saved_amount + deposit_amount
    should_trigger = (
        not fee_already_collected
        and new_cumulative >= assigned_value_milestone
    )

    payout_fee: int = TARGET_PAYOUT_FEE if should_trigger else 0
    final_charge: int = base.charge_amount + payout_fee

    return FlexibleRotateDepositResult(
        deposit_amount=deposit_amount,
        base_charge_amount=base.charge_amount,
        mtn_deposit_fee=base.mtn_fee,
        microbond_base_fee=base.platform_fee,
        hidden_payout_fee=payout_fee,
        final_charge_amount=final_charge,
        milestone_triggered_now=should_trigger,
        new_cumulative_total=new_cumulative,
        assigned_value_milestone=assigned_value_milestone,
    )
