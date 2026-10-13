from app.services.fee_engines.base_deposit_fee.schemas.deposit_fee_breakdown import TIER_TABLE


def get_psychological_offset(group_target_amount: int) -> int:
    """
    Look up the psychological offset for a given deposit amount.
    Matches the first tier whose upper boundary exceeds the deposit.
    """
    for max_ugx, offset in TIER_TABLE:
        if max_ugx is None or group_target_amount < max_ugx:
            return offset
    return TIER_TABLE[-1][1]
