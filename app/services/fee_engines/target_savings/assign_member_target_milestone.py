from typing import Optional
import numpy as np
from app.services.fee_engines.target_savings.schemas.target_deposit_calculation import (
    MILESTONE_THRESHOLDS,
)


def assign_member_target_milestone(random_seed: Optional[int] = None) -> float:
    """
    Randomly assign a percentage milestone threshold to a member at join time.
    The result must be stored in the database immediately (e.g. as
    `GroupMembership.fee_milestone_threshold`).

    Called ONCE per member when they commit to a target savings goal.
    Never called again for the same goal — the result is immutable.
    """
    rng = np.random.default_rng(random_seed)
    return float(rng.choice(MILESTONE_THRESHOLDS))
