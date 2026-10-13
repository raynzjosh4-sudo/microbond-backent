from dataclasses import dataclass
from typing import Dict, List, Any

# Percentage points of total cycle commitment at which the fee may trigger.
MILESTONE_PERCENTAGES: List[float] = [0.20, 0.50, 0.80]

MILESTONE_LABEL: Dict[float, str] = {
    0.20: "EARLY_20PCT",
    0.50: "MID_50PCT",
    0.80: "LATE_80PCT",
}


@dataclass(frozen=True)
class FlexibleRotateDepositResult:
    """
    Result of a single flexible deposit calculation for a Rotating Group.
    """
    deposit_amount: int
    base_charge_amount: int
    mtn_deposit_fee: int
    microbond_base_fee: int
    hidden_payout_fee: int
    final_charge_amount: int
    milestone_triggered_now: bool
    new_cumulative_total: int
    assigned_value_milestone: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "deposit_amount": self.deposit_amount,
            "base_charge_amount": self.base_charge_amount,
            "mtn_deposit_fee": self.mtn_deposit_fee,
            "microbond_base_fee": self.microbond_base_fee,
            "hidden_payout_fee": self.hidden_payout_fee,
            "final_charge_amount": self.final_charge_amount,
            "milestone_triggered_now": self.milestone_triggered_now,
            "new_cumulative_total": self.new_cumulative_total,
        }
