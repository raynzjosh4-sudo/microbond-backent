from app.services.fee_engines.base_deposit_fee import calculate_deposit_fee, DepositFeeBreakdown
from app.services.fee_engines.rotating.amortizer.get_charge_for_deposit import (
    get_charge_for_deposit,
)
from app.services.fee_engines.rotating.amortizer.schemas.member_deposit_schedule import (
    TARGET_PAYOUT_FEE,
)
from app.services.fee_engines.rotating.resolver.schemas.deposit_status import DepositStatus
from app.services.fee_engines.rotating.resolver.schemas.deposit_breakdown import (
    DepositBreakdown,
)
from app.services.fee_engines.rotating.resolver.schemas.deposit_resolution import (
    DepositResolution,
)
from app.services.fee_engines.rotating.resolver.helpers.build_rejection import (
    build_rejection,
)
from app.services.fee_engines.rotating.resolver.helpers.classify_payment import (
    classify_payment,
)


def resolve_deposit_intent(
    entered_amount: int,
    contribution_amount: int,
    amount_paid_this_cycle: int,
    accumulated_arrears: int,
    unpaid_penalties_ugx: int,
    milestone_round_number: int,
    current_round_number: int,
    allow_partial: bool,
    allow_advance: bool,
) -> DepositResolution:
    """
    Resolve a member's deposit intent for a Rotating Group (MERRY_GO_ROUND).
    """
    if entered_amount <= 0:
        return build_rejection("Deposit amount must be greater than 0 UGX.")

    current_remaining = max(0, contribution_amount - amount_paid_this_cycle)
    total_outstanding = current_remaining + accumulated_arrears + unpaid_penalties_ugx
    has_arrears = accumulated_arrears > 0 or unpaid_penalties_ugx > 0

    is_underpayment = total_outstanding > 0 and entered_amount < total_outstanding
    is_overpayment  = total_outstanding > 0 and entered_amount > total_outstanding

    if is_underpayment and not allow_partial:
        outstanding_fmt = f"{total_outstanding:,}"
        detail = (
            f"Partial payments are not allowed in this group. "
            f"Please deposit the full outstanding amount of {outstanding_fmt} UGX."
        )
        if has_arrears:
            detail += (
                f" This includes {accumulated_arrears:,} UGX in arrears"
                f" and {unpaid_penalties_ugx:,} UGX in late fees."
            )
        return build_rejection(detail)

    if is_overpayment and not allow_advance and total_outstanding > 0:
        return build_rejection(
            f"Advance payments are not allowed in this group. "
            f"Please deposit exactly {total_outstanding:,} UGX."
        )

    amount_to_credit     = entered_amount
    surplus_forward      = max(0, entered_amount - total_outstanding) if total_outstanding > 0 else 0
    shortfall_remaining  = max(0, total_outstanding - entered_amount)

    final_charge_amount = get_charge_for_deposit(
        group_target_amount=entered_amount,
        member_milestone_round=milestone_round_number,
        current_round_number=current_round_number,
    )

    base: DepositFeeBreakdown = calculate_deposit_fee(entered_amount)
    is_milestone = (current_round_number == milestone_round_number)
    milestone_fee = TARGET_PAYOUT_FEE if is_milestone else 0
    total_fee = (final_charge_amount - entered_amount)

    payment_type = classify_payment(
        entered=entered_amount,
        total_outstanding=total_outstanding,
        has_arrears=has_arrears,
        is_partial=is_underpayment,
        is_advance=is_overpayment,
    )

    if is_underpayment:
        deposit_status = DepositStatus.APPROVED_PARTIAL
    elif is_overpayment:
        deposit_status = DepositStatus.APPROVED_ADVANCE
    else:
        deposit_status = DepositStatus.APPROVED

    summary_parts = [
        f"You will be charged {final_charge_amount:,} UGX.",
        f"This covers your {entered_amount:,} UGX contribution",
        f"+ {total_fee:,} UGX processing fee.",
    ]
    if is_milestone:
        summary_parts.append("(Includes a one-time network recovery charge.)")
    if surplus_forward > 0:
        summary_parts.append(
            f"{surplus_forward:,} UGX will be credited toward your next cycle."
        )
    if shortfall_remaining > 0:
        summary_parts.append(
            f"You still owe {shortfall_remaining:,} UGX after this deposit."
        )
    if has_arrears:
        summary_parts.append(
            f"Includes {accumulated_arrears:,} UGX arrears + {unpaid_penalties_ugx:,} UGX late fees."
        )

    breakdown = DepositBreakdown(
        current_cycle_due=contribution_amount,
        amount_already_paid=amount_paid_this_cycle,
        current_cycle_remaining=current_remaining,
        arrears_owed=accumulated_arrears,
        penalties_owed=unpaid_penalties_ugx,
        total_outstanding=total_outstanding,
        entered_amount=entered_amount,
        amount_to_credit=amount_to_credit,
        surplus_credited_forward=surplus_forward,
        shortfall_remaining=shortfall_remaining,
        mtn_collection_fee=base.mtn_fee,
        microbond_base_fee=base.platform_fee,
        milestone_payout_fee=milestone_fee,
        total_fee=total_fee,
        final_charge_amount=final_charge_amount,
        is_milestone_deposit=is_milestone,
    )

    return DepositResolution(
        status=deposit_status,
        payment_type=payment_type,
        rejection_reason=None,
        breakdown=breakdown,
        final_charge_amount=final_charge_amount,
        display_summary=" ".join(summary_parts),
    )
