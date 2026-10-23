import json
from app.services.fee_engines.investment_club.schemas.investment_deposit_calculation import (
    InvestmentDepositCalculation,
    TARGET_PAYOUT_FEE,
    DEPOSIT_COUNT_MILESTONES,
)
from app.core.microbond_core import calculate_investment_deposit_fee as core_calculate_investment_fee


def calculate_investment_group_deposit(
    deposit_amount: int,
    current_annual_deposit_count: int,
    assigned_milestone_count: int,
    fee_collected_this_year: bool,
) -> InvestmentDepositCalculation:
    """
    Calculate the exact MTN RequestToPay charge for a share purchase deposit
    in an Investment Club / Open-Ended Chama using the microbond_core engine.
    """
    if not isinstance(deposit_amount, int) or deposit_amount <= 0:
        raise ValueError(f"deposit_amount must be a positive int. Got: {deposit_amount!r}")
    if assigned_milestone_count not in DEPOSIT_COUNT_MILESTONES:
        raise ValueError(
            f"assigned_milestone_count must be one of {DEPOSIT_COUNT_MILESTONES}. "
            f"Got: {assigned_milestone_count!r}"
        )

    raw = core_calculate_investment_fee(
        deposit_amount=deposit_amount,
        current_annual_deposit_count=current_annual_deposit_count,
        assigned_milestone_count=assigned_milestone_count,
        fee_collected_this_year=fee_collected_this_year,
        target_payout_fee=TARGET_PAYOUT_FEE,
    )
    res = json.loads(raw)

    return InvestmentDepositCalculation(
        deposit_amount=res["deposit_amount"],
        base_charge_amount=res["base_charge_amount"],
        mtn_deposit_fee=res["mtn_deposit_fee"],
        microbond_deposit_fee=res["microbond_deposit_fee"],
        hidden_payout_fee=res["hidden_payout_fee"],
        final_charge_amount=res["final_charge_amount"],
        is_fee_milestone=res["is_fee_milestone"],
        this_deposit_number=res["this_deposit_number"],
    )

