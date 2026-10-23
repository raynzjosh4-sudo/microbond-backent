import json
from app.services.fee_engines.base_deposit_fee.schemas.deposit_fee_breakdown import (
    DepositFeeBreakdown,
)
from app.core.microbond_core import calculate_base_deposit_fee as core_calculate_base_fee


def calculate_deposit_fee(group_target_amount: int) -> DepositFeeBreakdown:
    """
    Calculate the complete deposit fee breakdown for a Microbond savings
    group deposit using the authoritative microbond_core domain engine.
    """
    if not isinstance(group_target_amount, int) or group_target_amount <= 0:
        raise ValueError(
            f"group_target_amount must be a positive integer (UGX). "
            f"Got: {group_target_amount!r}"
        )

    res = json.loads(core_calculate_base_fee(group_target_amount))

    return DepositFeeBreakdown(
        group_target_amount=res["group_target_amount"],
        mtn_fee=res["mtn_fee"],
        platform_fee=res["platform_fee"],
        total_fee=res["total_fee"],
        charge_amount=res["charge_amount"],
        psychological_offset=res["psychological_offset"],
        microbond_net_revenue=res["microbond_net_revenue"],
    )

