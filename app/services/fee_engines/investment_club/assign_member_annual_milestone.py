from typing import Optional
import numpy as np
from app.services.fee_engines.investment_club.schemas.investment_deposit_calculation import (
    DEPOSIT_COUNT_MILESTONES,
)


def assign_member_annual_milestone(random_seed: Optional[int] = None) -> int:
    """
    Randomly assign a deposit-count milestone to a member for the upcoming
    accounting year. The result must be stored in the database immediately.

    Called ONCE per member per accounting year — either when they join the
    club, or by the New Year cron job that resets all member counters.
    """
    rng = np.random.default_rng(random_seed)
    return int(rng.choice(DEPOSIT_COUNT_MILESTONES))
