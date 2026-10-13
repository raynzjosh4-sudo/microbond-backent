from app.services.fee_engines.target_savings.schemas.target_deposit_calculation import (
    MILESTONE_LABEL,
)


def get_milestone_label(threshold: float) -> str:
    """
    Return the human-readable audit label for a milestone threshold.
    Safe to call with any stored DB value — returns 'UNKNOWN' if unrecognized.
    """
    return MILESTONE_LABEL.get(threshold, "UNKNOWN")
