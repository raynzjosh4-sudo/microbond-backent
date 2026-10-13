from app.services.fee_engines.rotating.amortizer.schemas.member_deposit_schedule import (
    MILESTONE_START,
    MILESTONE_MIDDLE,
)


def resolve_milestone_round(total_rounds: int, milestone_type: str) -> int:
    """
    Convert a milestone label to its actual 1-based round number.
    """
    if milestone_type == MILESTONE_START:
        return 1
    elif milestone_type == MILESTONE_MIDDLE:
        return max(1, total_rounds // 2)
    else:  # MILESTONE_LAST
        return total_rounds
