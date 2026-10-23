import json
from typing import Dict, Optional
from app.services.fee_engines.rotating.surplus.schemas.coverage_status import CoverageStatus
from app.services.fee_engines.rotating.surplus.schemas.cycle_coverage_detail import (
    CycleCoverageDetail,
)
from app.services.fee_engines.rotating.surplus.schemas.surplus_allocation_result import (
    SurplusAllocationResult,
)
from app.core.microbond_core import allocate_surplus_waterfall


def allocate_surplus_to_future_cycles(
    surplus_amount_ugx: int,
    current_cycle_number: int,
    standard_contribution_amount: int,
    cycle_specific_obligations: Optional[Dict[int, int]] = None,
    max_cycles_in_group: Optional[int] = None,
) -> SurplusAllocationResult:
    """
    Allocate an advance overpayment across subsequent cycles using a strict
    chronological FIFO waterfall powered by the microbond_core domain engine.
    """
    raw = allocate_surplus_waterfall(
        surplus_amount=surplus_amount_ugx,
        current_cycle_number=current_cycle_number,
        standard_contribution=standard_contribution_amount,
        cycle_overrides=cycle_specific_obligations,
        max_cycles=max_cycles_in_group,
    )
    data = json.loads(raw)

    breakdown = []
    partial_detail = None

    for item in data.get("coverage_details", []):
        detail = CycleCoverageDetail(
            cycle_number=item["cycle_number"],
            amount_required=item["amount_required"],
            amount_allocated=item["amount_allocated"],
            shortfall=item["shortfall"],
            status=CoverageStatus(item["status"]),
        )
        breakdown.append(detail)
        if detail.status == CoverageStatus.PARTIALLY_COVERED:
            partial_detail = detail

    return SurplusAllocationResult(
        total_surplus_ugx=data.get("total_surplus", 0),
        cycles_fully_covered_count=data.get("cycles_fully_covered_count", 0),
        fully_covered_cycles=data.get("fully_covered_cycles", []),
        partially_covered_cycle=partial_detail,
        unallocated_residual_ugx=data.get("unallocated_residual", 0),
        next_cycle_requiring_payment=data.get("next_cycle_requiring_payment", current_cycle_number + 1),
        coverage_breakdown=breakdown,
        summary_label=data.get("summary_label", ""),
    )
