from app.services.fee_engines.investment_club.schemas.investment_deposit_calculation import (
    MILESTONE_LABEL,
)


def get_milestone_label(count: int) -> str:
    """
    Return the human-readable audit label for a deposit-count milestone.
    Safe to call with any stored DB value — returns 'UNKNOWN' if unrecognized.
    """
    return MILESTONE_LABEL.get(count, "UNKNOWN")
