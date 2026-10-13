from app.services.fee_engines.rotating.surplus.schemas.contribution_adjustment_result import (
    ContributionAdjustmentResult,
)


def recalculate_credit_on_contribution_change(
    existing_credit_balance_ugx: int,
    old_contribution_amount_ugx: int,
    new_contribution_amount_ugx: int,
    current_cycle_number: int,
) -> ContributionAdjustmentResult:
    """
    Re-evaluate a member's advance credit when the group votes to change its
    contribution target (e.g. from 50,000 to 60,000 UGX).
    """
    if new_contribution_amount_ugx <= 0:
        raise ValueError("New contribution amount must be strictly positive.")

    if existing_credit_balance_ugx <= 0:
        return ContributionAdjustmentResult(
            existing_credit_balance_ugx=0,
            old_contribution_amount_ugx=old_contribution_amount_ugx,
            new_contribution_amount_ugx=new_contribution_amount_ugx,
            new_cycles_fully_covered=0,
            partial_cycle_number=None,
            partial_cycle_credit_applied=0,
            partial_cycle_shortfall=0,
            user_advisory_message="No advance credit on file to revalue.",
        )

    full_cycles = existing_credit_balance_ugx // new_contribution_amount_ugx
    remainder = existing_credit_balance_ugx % new_contribution_amount_ugx

    partial_cycle = None
    applied_to_partial = 0
    shortfall = 0

    if remainder > 0:
        partial_cycle = current_cycle_number + full_cycles + 1
        applied_to_partial = remainder
        shortfall = new_contribution_amount_ugx - remainder

    if full_cycles > 0 and partial_cycle is not None:
        msg = (
            f"The group contribution changed from {old_contribution_amount_ugx:,} UGX "
            f"to {new_contribution_amount_ugx:,} UGX. Your advance credit of {existing_credit_balance_ugx:,} UGX "
            f"now fully covers {full_cycles} cycle(s), with {applied_to_partial:,} UGX applied "
            f"toward Cycle {partial_cycle}. You will have a small top-up of {shortfall:,} UGX due for Cycle {partial_cycle}."
        )
    elif full_cycles > 0:
        msg = (
            f"The group contribution changed to {new_contribution_amount_ugx:,} UGX. "
            f"Your credit of {existing_credit_balance_ugx:,} UGX perfectly covers {full_cycles} full cycle(s)."
        )
    else:
        msg = (
            f"The group contribution changed to {new_contribution_amount_ugx:,} UGX. "
            f"Your advance credit of {existing_credit_balance_ugx:,} UGX is applied to Cycle {current_cycle_number + 1}. "
            f"Remaining balance due: {shortfall:,} UGX."
        )

    return ContributionAdjustmentResult(
        existing_credit_balance_ugx=existing_credit_balance_ugx,
        old_contribution_amount_ugx=old_contribution_amount_ugx,
        new_contribution_amount_ugx=new_contribution_amount_ugx,
        new_cycles_fully_covered=full_cycles,
        partial_cycle_number=partial_cycle,
        partial_cycle_credit_applied=applied_to_partial,
        partial_cycle_shortfall=shortfall,
        user_advisory_message=msg,
    )
