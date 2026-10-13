from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ContributionAdjustmentResult:
    """
    Result of re-evaluating existing advance credit when the group votes
    to change its standard contribution amount.
    """
    existing_credit_balance_ugx: int
    old_contribution_amount_ugx: int
    new_contribution_amount_ugx: int
    new_cycles_fully_covered: int
    partial_cycle_number: Optional[int]
    partial_cycle_credit_applied: int
    partial_cycle_shortfall: int
    user_advisory_message: str
