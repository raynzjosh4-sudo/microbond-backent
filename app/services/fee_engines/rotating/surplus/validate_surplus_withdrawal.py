from app.services.fee_engines.rotating.surplus.schemas.withdrawal_eligibility_status import (
    WithdrawalEligibilityStatus,
)
from app.services.fee_engines.rotating.surplus.schemas.surplus_withdrawal_evaluation import (
    SurplusWithdrawalEvaluation,
)


def validate_surplus_withdrawal(
    member_credit_balance_ugx: int,
    requested_withdrawal_ugx: int,
    group_pool_liquid_balance_ugx: int,
    upcoming_cycle_payout_amount_ugx: int,
    hours_since_deposit: float,
    signer_approvals_count: int,
    required_signer_approvals: int = 1,
    cooldown_timelock_hours: float = 2.0,
    momo_disbursement_fee_ugx: int = 1000,
    min_liquidity_reserve_pct: float = 0.05,
) -> SurplusWithdrawalEvaluation:
    """
    Validate and guard a member's request to withdraw an accidental overpayment.
    """
    if requested_withdrawal_ugx <= momo_disbursement_fee_ugx:
        return SurplusWithdrawalEvaluation(
            status=WithdrawalEligibilityStatus.BELOW_MINIMUM_THRESHOLD,
            is_eligible=False,
            requested_amount_ugx=requested_withdrawal_ugx,
            approved_gross_amount_ugx=0,
            telecom_disbursement_fee_ugx=momo_disbursement_fee_ugx,
            net_payout_to_member_ugx=0,
            remaining_credit_after_refund=member_credit_balance_ugx,
            group_pool_balance_after_refund=group_pool_liquid_balance_ugx,
            reason_message=(
                f"Requested withdrawal ({requested_withdrawal_ugx:,} UGX) must exceed "
                f"the network transfer fee of {momo_disbursement_fee_ugx:,} UGX."
            ),
        )

    if requested_withdrawal_ugx > member_credit_balance_ugx:
        return SurplusWithdrawalEvaluation(
            status=WithdrawalEligibilityStatus.EXCEEDS_CREDIT_BALANCE,
            is_eligible=False,
            requested_amount_ugx=requested_withdrawal_ugx,
            approved_gross_amount_ugx=0,
            telecom_disbursement_fee_ugx=momo_disbursement_fee_ugx,
            net_payout_to_member_ugx=0,
            remaining_credit_after_refund=member_credit_balance_ugx,
            group_pool_balance_after_refund=group_pool_liquid_balance_ugx,
            reason_message=(
                f"Cannot withdraw {requested_withdrawal_ugx:,} UGX. "
                f"Your unallocated advance credit is only {member_credit_balance_ugx:,} UGX. "
                f"(Current cycle dues are committed to the round pot and cannot be refunded)."
            ),
        )

    min_required_pool = upcoming_cycle_payout_amount_ugx + int(
        group_pool_liquid_balance_ugx * min_liquidity_reserve_pct
    )
    pool_after_withdrawal = group_pool_liquid_balance_ugx - requested_withdrawal_ugx

    if pool_after_withdrawal < min_required_pool:
        return SurplusWithdrawalEvaluation(
            status=WithdrawalEligibilityStatus.INSUFFICIENT_POOL_CASH,
            is_eligible=False,
            requested_amount_ugx=requested_withdrawal_ugx,
            approved_gross_amount_ugx=0,
            telecom_disbursement_fee_ugx=momo_disbursement_fee_ugx,
            net_payout_to_member_ugx=0,
            remaining_credit_after_refund=member_credit_balance_ugx,
            group_pool_balance_after_refund=group_pool_liquid_balance_ugx,
            reason_message=(
                f"Withdrawal temporarily restricted: processing this refund would leave "
                f"the group pool with {pool_after_withdrawal:,} UGX, which is below the "
                f"{min_required_pool:,} UGX needed to guarantee the scheduled round payout. "
                f"Wait until the current round payout clears or contact the Group Treasurer."
            ),
        )

    if hours_since_deposit < cooldown_timelock_hours:
        remaining_wait = round(cooldown_timelock_hours - hours_since_deposit, 1)
        return SurplusWithdrawalEvaluation(
            status=WithdrawalEligibilityStatus.TIMELOCK_ACTIVE,
            is_eligible=False,
            requested_amount_ugx=requested_withdrawal_ugx,
            approved_gross_amount_ugx=0,
            telecom_disbursement_fee_ugx=momo_disbursement_fee_ugx,
            net_payout_to_member_ugx=0,
            remaining_credit_after_refund=member_credit_balance_ugx,
            group_pool_balance_after_refund=group_pool_liquid_balance_ugx,
            reason_message=(
                f"Security timelock active: please allow {remaining_wait} more hour(s) "
                f"before initiating a reversal. This prevents duplicate mobile money processing."
            ),
        )

    if signer_approvals_count < required_signer_approvals:
        return SurplusWithdrawalEvaluation(
            status=WithdrawalEligibilityStatus.PENDING_APPROVALS,
            is_eligible=False,
            requested_amount_ugx=requested_withdrawal_ugx,
            approved_gross_amount_ugx=0,
            telecom_disbursement_fee_ugx=momo_disbursement_fee_ugx,
            net_payout_to_member_ugx=0,
            remaining_credit_after_refund=member_credit_balance_ugx,
            group_pool_balance_after_refund=group_pool_liquid_balance_ugx,
            reason_message=(
                f"Refund request is pending approval from the Group Treasurer or Admin "
                f"({signer_approvals_count}/{required_signer_approvals} approvals logged)."
            ),
        )

    net_payout = requested_withdrawal_ugx - momo_disbursement_fee_ugx
    remaining_credit = member_credit_balance_ugx - requested_withdrawal_ugx

    return SurplusWithdrawalEvaluation(
        status=WithdrawalEligibilityStatus.ELIGIBLE,
        is_eligible=True,
        requested_amount_ugx=requested_withdrawal_ugx,
        approved_gross_amount_ugx=requested_withdrawal_ugx,
        telecom_disbursement_fee_ugx=momo_disbursement_fee_ugx,
        net_payout_to_member_ugx=net_payout,
        remaining_credit_after_refund=remaining_credit,
        group_pool_balance_after_refund=pool_after_withdrawal,
        reason_message=(
            f"Withdrawal approved. {net_payout:,} UGX will be sent to your registered "
            f"Mobile Money number ({requested_withdrawal_ugx:,} UGX refund minus "
            f"{momo_disbursement_fee_ugx:,} UGX network transfer fee). "
            f"Remaining advance credit: {remaining_credit:,} UGX."
        ),
    )
