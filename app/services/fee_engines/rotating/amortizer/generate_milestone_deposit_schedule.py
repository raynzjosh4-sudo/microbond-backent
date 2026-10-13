from typing import Optional, List
import numpy as np

from app.services.fee_engines.base_deposit_fee import calculate_deposit_fee, DepositFeeBreakdown
from app.services.fee_engines.rotating.amortizer.schemas.member_deposit_schedule import (
    MemberDepositSchedule,
    TARGET_PAYOUT_FEE,
)
from app.services.fee_engines.rotating.amortizer.helpers.pick_milestone_for_member import (
    pick_milestone_for_member,
)
from app.services.fee_engines.rotating.amortizer.helpers.resolve_milestone_round import (
    resolve_milestone_round,
)


def generate_milestone_deposit_schedule(
    group_target_amount: int,
    total_members: int,
    total_rounds: int,
    random_seed: Optional[int] = None,
) -> List[MemberDepositSchedule]:
    """
    Generate the complete deposit schedule for all members of a rotating
    savings group. Must be called ONCE at group creation and persisted.
    """
    if not isinstance(group_target_amount, int) or group_target_amount <= 0:
        raise ValueError(f"group_target_amount must be a positive int. Got: {group_target_amount!r}")
    if not isinstance(total_members, int) or total_members < 2:
        raise ValueError(f"total_members must be >= 2. Got: {total_members!r}")
    if not isinstance(total_rounds, int) or total_rounds < 1:
        raise ValueError(f"total_rounds must be >= 1. Got: {total_rounds!r}")

    base: DepositFeeBreakdown = calculate_deposit_fee(group_target_amount)
    rng = np.random.default_rng(random_seed)

    schedules: List[MemberDepositSchedule] = []

    for member_index in range(1, total_members + 1):
        milestone_type: str = pick_milestone_for_member(rng)
        milestone_round: int = resolve_milestone_round(total_rounds, milestone_type)
        milestone_charge: int = base.charge_amount + TARGET_PAYOUT_FEE

        schedules.append(
            MemberDepositSchedule(
                member_index=member_index,
                total_rounds=total_rounds,
                group_target_amount=group_target_amount,
                base_charge_amount=base.charge_amount,
                milestone_round_number=milestone_round,
                milestone_type=milestone_type,
                milestone_charge_amount=milestone_charge,
                hidden_payout_fee=TARGET_PAYOUT_FEE,
                mtn_deposit_fee=base.mtn_fee,
                microbond_deposit_fee=base.platform_fee,
            )
        )

    return schedules
