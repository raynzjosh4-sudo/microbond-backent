from typing import Optional
import numpy as np
from app.services.fee_engines.rotating.amortizer.schemas.flexible_rotate_deposit_result import (
    MILESTONE_PERCENTAGES,
)


def assign_member_value_milestone(
    contribution_amount: int,
    total_rounds: int,
    random_seed: Optional[int] = None,
) -> int:
    """
    Assign a UGX value threshold to a member at group creation.
    Store the result in the DB as `GroupMembership.fee_milestone_value_ugx`.
    """
    rng = np.random.default_rng(random_seed)
    pct = float(rng.choice(MILESTONE_PERCENTAGES))
    total_cycle_commitment = contribution_amount * total_rounds
    return int(total_cycle_commitment * pct)
