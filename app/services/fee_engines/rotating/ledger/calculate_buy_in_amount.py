from datetime import datetime, timezone
from typing import Dict, Any, Optional


def calculate_buy_in_amount(
    contribution_amount: int,
    collection_frequency_days: int,
    group_start_time_ms: int,
    member_joined_at_ms: int,
    current_time_ms: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Calculate the lump-sum buy-in a new mid-cycle joiner must pay when
    the group policy is BUY_IN_REQUIRED.
    """
    pre_join_elapsed_ms = max(0, member_joined_at_ms - group_start_time_ms)
    pre_join_days = pre_join_elapsed_ms // 86_400_000
    cycles_before_join = int(pre_join_days // collection_frequency_days)

    buy_in_ugx = cycles_before_join * contribution_amount
    is_required = cycles_before_join > 0

    label = (
        f"Buy-in required: {buy_in_ugx:,} UGX (covers {cycles_before_join} missed cycle(s))"
        if is_required
        else "No buy-in required — you are joining before the first cycle ends."
    )

    return {
        "buy_in_amount_ugx": buy_in_ugx,
        "cycles_elapsed": cycles_before_join,
        "is_buy_in_required": is_required,
        "display_label": label,
    }
