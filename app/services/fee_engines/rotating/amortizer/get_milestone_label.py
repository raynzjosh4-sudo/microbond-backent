from app.services.fee_engines.rotating.amortizer.schemas.flexible_rotate_deposit_result import (
    MILESTONE_LABEL,
)


def get_milestone_label(pct: float) -> str:
    """Human-readable audit label for a milestone percentage."""
    return MILESTONE_LABEL.get(pct, "UNKNOWN")
