from app.services.fee_engines.base_deposit_fee.schemas.deposit_fee_breakdown import (
    DepositFeeBreakdown,
    MTN_RATE,
)
from app.services.fee_engines.base_deposit_fee.helpers.get_psychological_offset import (
    get_psychological_offset,
)


def calculate_deposit_fee(group_target_amount: int) -> DepositFeeBreakdown:
    """
    Calculate the complete deposit fee breakdown for a Microbond savings
    group deposit using the psychological pricing strategy.

    Parameters
    ----------
    group_target_amount : int
        The exact UGX amount the user wants credited to their savings pool.
        Must be a positive integer (whole UGX, no fractions).

    Returns
    -------
    DepositFeeBreakdown
        Frozen dataclass with all fee components and the final charge
        amount to pass to the MTN MoMo RequestToPay API.

    Raises
    ------
    ValueError
        If `group_target_amount` is not a positive integer.
    """
    if not isinstance(group_target_amount, int) or group_target_amount <= 0:
        raise ValueError(
            f"group_target_amount must be a positive integer (UGX). "
            f"Got: {group_target_amount!r}"
        )

    offset = get_psychological_offset(group_target_amount)

    # MTN's 1.5% fee — calculated on the base deposit amount, rounded to UGX
    mtn_fee: int = round(group_target_amount * MTN_RATE)

    # Platform fee: the psychological irregular number.
    # Clamped to 0 to guard against tiny deposits where offset > mtn_fee.
    platform_fee: int = max(0, mtn_fee - offset)

    total_fee: int = mtn_fee + platform_fee
    charge_amount: int = group_target_amount + total_fee

    # Net Microbond revenue after MTN deducts their 1.5% from charge_amount.
    microbond_net_revenue: int = platform_fee

    return DepositFeeBreakdown(
        group_target_amount=group_target_amount,
        mtn_fee=mtn_fee,
        platform_fee=platform_fee,
        total_fee=total_fee,
        charge_amount=charge_amount,
        psychological_offset=offset,
        microbond_net_revenue=microbond_net_revenue,
    )
