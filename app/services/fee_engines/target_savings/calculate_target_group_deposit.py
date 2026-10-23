import json
from app.services.fee_engines.target_savings.schemas.target_deposit_calculation import (
    TargetDepositCalculation,
    TARGET_PAYOUT_FEE,
    MILESTONE_THRESHOLDS,
)
from app.core.microbond_core import calculate_target_deposit_fee as core_calculate_target_fee


def calculate_target_group_deposit(
    deposit_amount: int,
    current_saved_amount: int,
    target_goal_amount: int,
    assigned_milestone_threshold: float,
    fee_already_collected: bool,
) -> TargetDepositCalculation:
    """
    Calculate the exact MTN RequestToPay charge for a deposit in a
    Target / Goal-Based Savings Group using the authoritative microbond_core engine.
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

    raw = core_calculate_target_fee(
        deposit_amount=deposit_amount,
        current_saved_amount=current_saved_amount,
        target_goal_amount=target_goal_amount,
        assigned_milestone_threshold=assigned_milestone_threshold,
        fee_already_collected=fee_already_collected,
        target_payout_fee=TARGET_PAYOUT_FEE,
    )
    res = json.loads(raw)

    return TargetDepositCalculation(
        deposit_amount=res["deposit_amount"],
        base_charge_amount=res["base_charge_amount"],
        mtn_deposit_fee=res["mtn_deposit_fee"],
        microbond_deposit_fee=res["microbond_deposit_fee"],
        hidden_payout_fee=res["hidden_payout_fee"],
        final_charge_amount=res["final_charge_amount"],
        is_fee_milestone=res["is_fee_milestone"],
        milestone_triggered_now=res["milestone_triggered_now"],
    )

