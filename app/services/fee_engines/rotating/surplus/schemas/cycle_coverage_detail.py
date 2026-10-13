from dataclasses import dataclass
from app.services.fee_engines.rotating.surplus.schemas.coverage_status import CoverageStatus


@dataclass(frozen=True)
class CycleCoverageDetail:
    """Breakdown of how advance credit applies to a specific cycle."""
    cycle_number: int
    amount_required: int
    amount_allocated: int
    shortfall: int
    status: CoverageStatus
