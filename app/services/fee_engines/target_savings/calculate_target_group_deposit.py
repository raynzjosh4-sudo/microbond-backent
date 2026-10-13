from app.services.fee_engines.base_deposit_fee import calculate_deposit_fee, DepositFeeBreakdown
from app.services.fee_engines.target_savings.schemas.target_deposit_calculation import (
    TargetDepositCalculation,
    TARGET_PAYOUT_FEE,
    MILESTONE_THRESHOLDS,
)


def calculate_target_group_deposit(
    deposit_amount: int,
    current_saved_amount: int,
    target_goal_amount: int,
    assigned_milestone_threshold: float,
    fee_already_collected: bool,
) -> TargetDepositCalculation:
    """
    Calculate the exact MTN RequestToPay charge for a deposit in a
    Target / Goal-Based Savings Group.

    Injects the 979 UGX payout fee on the first deposit where the member's
    cumulative savings crosses their assigned milestone threshold. All other
    deposits carry only the standard psychological pricing fees.
    """
    if not isinstance(deposit_amount, int) or deposit_amount <= 0:
        raise ValueError(f"deposit_amount must be a positive int. Got: {deposit_amount!r}")
    if not isinstance(target_goal_amount, int) or target_goal_amount <= 0:
        raise ValueError(f"target_goal_amount must be a positive int. Got: {target_goal_amount!r}")
    if assigned_milestone_threshold not in MILESTONE_THRESHOLDS:
        raise ValueError(
            f"assigned_milestone_threshold must be one of {MILESTONE_THRESHOLDS}. "
            f"Got: {assigned_milestone_threshold!r}"
        )

    base: DepositFeeBreakdown = calculate_deposit_fee(deposit_amount)

    should_charge_milestone = False
    if not fee_already_collected:
        new_cumulative = current_saved_amount + deposit_amount
        threshold_amount = target_goal_amount * assigned_milestone_threshold

        if new_cumulative >= threshold_amount or new_cumulative >= target_goal_amount:
            should_charge_milestone = True

    payout_fee: int = TARGET_PAYOUT_FEE if should_charge_milestone else 0
    final_charge: int = base.charge_amount + payout_fee

    return TargetDepositCalculation(
        deposit_amount=deposit_amount,
        base_charge_amount=base.charge_amount,
        mtn_deposit_fee=base.mtn_fee,
        microbond_deposit_fee=base.platform_fee,
        hidden_payout_fee=payout_fee,
        final_charge_amount=final_charge,
        is_fee_milestone=should_charge_milestone,
        milestone_triggered_now=should_charge_milestone,
    )
