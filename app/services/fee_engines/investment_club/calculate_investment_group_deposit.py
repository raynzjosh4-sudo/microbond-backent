from app.services.fee_engines.base_deposit_fee import calculate_deposit_fee, DepositFeeBreakdown
from app.services.fee_engines.investment_club.schemas.investment_deposit_calculation import (
    InvestmentDepositCalculation,
    TARGET_PAYOUT_FEE,
    DEPOSIT_COUNT_MILESTONES,
)


def calculate_investment_group_deposit(
    deposit_amount: int,
    current_annual_deposit_count: int,
    assigned_milestone_count: int,
    fee_collected_this_year: bool,
) -> InvestmentDepositCalculation:
    """
    Calculate the exact MTN RequestToPay charge for a share purchase deposit
    in an Investment Club / Open-Ended Chama.

    Injects the 979 UGX annual payout fee on the first deposit where the
    member's annual deposit counter reaches or exceeds their assigned
    milestone count. All prior deposits are standard. Once triggered, all
    remaining deposits that year are also standard.
    """
    if not isinstance(deposit_amount, int) or deposit_amount <= 0:
        raise ValueError(f"deposit_amount must be a positive int. Got: {deposit_amount!r}")
    if assigned_milestone_count not in DEPOSIT_COUNT_MILESTONES:
        raise ValueError(
            f"assigned_milestone_count must be one of {DEPOSIT_COUNT_MILESTONES}. "
            f"Got: {assigned_milestone_count!r}"
        )

    base: DepositFeeBreakdown = calculate_deposit_fee(deposit_amount)

    this_deposit_number: int = current_annual_deposit_count + 1

    should_charge_milestone = False
    if not fee_collected_this_year:
        if this_deposit_number >= assigned_milestone_count:
            should_charge_milestone = True

    payout_fee: int = TARGET_PAYOUT_FEE if should_charge_milestone else 0
    final_charge: int = base.charge_amount + payout_fee

    return InvestmentDepositCalculation(
        deposit_amount=deposit_amount,
        base_charge_amount=base.charge_amount,
        mtn_deposit_fee=base.mtn_fee,
        microbond_deposit_fee=base.platform_fee,
        hidden_payout_fee=payout_fee,
        final_charge_amount=final_charge,
        is_fee_milestone=should_charge_milestone,
        this_deposit_number=this_deposit_number,
    )
