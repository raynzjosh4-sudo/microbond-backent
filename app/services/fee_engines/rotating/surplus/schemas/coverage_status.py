from enum import Enum


class CoverageStatus(str, Enum):
    """Status of a future cycle obligation relative to advance credit."""
    FULLY_COVERED     = "FULLY_COVERED"     # 100% satisfied by advance credit
    PARTIALLY_COVERED = "PARTIALLY_COVERED" # Partially covered; deficit remaining
    UNCOVERED         = "UNCOVERED"         # No credit reached this cycle
