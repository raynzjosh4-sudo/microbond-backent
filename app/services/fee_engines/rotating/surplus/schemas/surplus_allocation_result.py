from dataclasses import dataclass
from typing import List, Optional
from app.services.fee_engines.rotating.surplus.schemas.cycle_coverage_detail import (
    CycleCoverageDetail,
)


@dataclass(frozen=True)
class SurplusAllocationResult:
    """
    Authoritative result of allocating surplus funds across future cycles.
    """
    total_surplus_ugx: int
    cycles_fully_covered_count: int
    fully_covered_cycles: List[int]
    partially_covered_cycle: Optional[CycleCoverageDetail]
    unallocated_residual_ugx: int
    next_cycle_requiring_payment: int
    coverage_breakdown: List[CycleCoverageDetail]
    summary_label: str
