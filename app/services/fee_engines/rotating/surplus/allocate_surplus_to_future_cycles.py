from typing import Dict, Optional
from app.services.fee_engines.rotating.surplus.schemas.coverage_status import CoverageStatus
from app.services.fee_engines.rotating.surplus.schemas.cycle_coverage_detail import (
    CycleCoverageDetail,
)
from app.services.fee_engines.rotating.surplus.schemas.surplus_allocation_result import (
    SurplusAllocationResult,
)


def allocate_surplus_to_future_cycles(
    surplus_amount_ugx: int,
    current_cycle_number: int,
    standard_contribution_amount: int,
    cycle_specific_obligations: Optional[Dict[int, int]] = None,
    max_cycles_in_group: Optional[int] = None,
) -> SurplusAllocationResult:
    """
    Allocate an advance overpayment across subsequent cycles using a strict
    chronological FIFO waterfall.
    """
    if surplus_amount_ugx <= 0:
        return SurplusAllocationResult(
            total_surplus_ugx=0,
            cycles_fully_covered_count=0,
            fully_covered_cycles=[],
            partially_covered_cycle=None,
            unallocated_residual_ugx=0,
            next_cycle_requiring_payment=current_cycle_number + 1,
            coverage_breakdown=[],
            summary_label="No advance surplus to allocate.",
        )

    remaining_surplus = surplus_amount_ugx
    target_cycle = current_cycle_number + 1
    fully_covered = []
    partial_detail = None
    breakdown = []

    while remaining_surplus > 0:
        if max_cycles_in_group is not None and target_cycle > max_cycles_in_group:
            break

        required_for_cycle = (
            cycle_specific_obligations.get(target_cycle, standard_contribution_amount)
            if cycle_specific_obligations
            else standard_contribution_amount
        )

        if remaining_surplus >= required_for_cycle:
            remaining_surplus -= required_for_cycle
            fully_covered.append(target_cycle)
            breakdown.append(
                CycleCoverageDetail(
                    cycle_number=target_cycle,
                    amount_required=required_for_cycle,
                    amount_allocated=required_for_cycle,
                    shortfall=0,
                    status=CoverageStatus.FULLY_COVERED,
                )
            )
            target_cycle += 1
        else:
            allocated = remaining_surplus
            shortfall = required_for_cycle - allocated
            partial_detail = CycleCoverageDetail(
                cycle_number=target_cycle,
                amount_required=required_for_cycle,
                amount_allocated=allocated,
                shortfall=shortfall,
                status=CoverageStatus.PARTIALLY_COVERED,
            )
            breakdown.append(partial_detail)
            remaining_surplus = 0
            break

    if partial_detail is not None:
        next_due_cycle = partial_detail.cycle_number
    elif fully_covered:
        next_due_cycle = fully_covered[-1] + 1
    else:
        next_due_cycle = current_cycle_number + 1

    if len(fully_covered) > 0 and partial_detail is not None:
        summary = (
            f"Advance covers {len(fully_covered)} full cycle(s) "
            f"(Cycles {fully_covered[0]}-{fully_covered[-1]}) + "
            f"{partial_detail.amount_allocated:,} UGX toward Cycle {partial_detail.cycle_number} "
            f"(Deficit remaining: {partial_detail.shortfall:,} UGX)."
        )
    elif len(fully_covered) > 0:
        cycles_str = (
            f"Cycle {fully_covered[0]}"
            if len(fully_covered) == 1
            else f"Cycles {fully_covered[0]}-{fully_covered[-1]}"
        )
        summary = (
            f"Advance completely clears {len(fully_covered)} future cycle(s) ({cycles_str}). "
            f"Next payment due on Cycle {next_due_cycle}."
        )
    elif partial_detail is not None:
        summary = (
            f"Advance credits {partial_detail.amount_allocated:,} UGX toward Cycle {partial_detail.cycle_number}. "
            f"Remaining deficit: {partial_detail.shortfall:,} UGX."
        )
    else:
        summary = f"{surplus_amount_ugx:,} UGX retained as general pool credit."

    return SurplusAllocationResult(
        total_surplus_ugx=surplus_amount_ugx,
        cycles_fully_covered_count=len(fully_covered),
        fully_covered_cycles=fully_covered,
        partially_covered_cycle=partial_detail,
        unallocated_residual_ugx=remaining_surplus,
        next_cycle_requiring_payment=next_due_cycle,
        coverage_breakdown=breakdown,
        summary_label=summary,
    )
