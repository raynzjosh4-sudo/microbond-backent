import numpy as np
from app.services.fee_engines.rotating.amortizer.schemas.member_deposit_schedule import (
    MILESTONE_START,
    MILESTONE_MIDDLE,
    MILESTONE_LAST,
)


def pick_milestone_for_member(rng: np.random.Generator) -> str:
    """
    Randomly select one of the three milestone positions for a single member
    using the provided numpy random Generator.
    """
    options = [MILESTONE_START, MILESTONE_MIDDLE, MILESTONE_LAST]
    return str(rng.choice(options))
