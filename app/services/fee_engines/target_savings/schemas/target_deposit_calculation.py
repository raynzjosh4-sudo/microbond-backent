from dataclasses import dataclass
from typing import Dict, List, Any

# MTN MoMo flat fee charged per disbursement
MTN_FLAT_PAYOUT_FEE: int = 300  # UGX

# Microbond platform profit retained per payout
MICROBOND_PAYOUT_PROFIT: int = 679  # UGX

# Total payout cost recovered per member per payout cycle
TARGET_PAYOUT_FEE: int = MTN_FLAT_PAYOUT_FEE + MICROBOND_PAYOUT_PROFIT  # 979 UGX

# The three percentage thresholds at which the hidden fee can be triggered:
MILESTONE_THRESHOLDS: List[float] = [0.20, 0.50, 1.00]

# Human-readable labels for logging / audit
MILESTONE_LABEL: Dict[float, str] = {
    0.20: "EARLY_20",
    0.50: "MID_50",
    1.00: "CLOSING_100",
}


@dataclass(frozen=True)
class TargetDepositCalculation:
    """
    Immutable result of a single deposit calculation in a Target Savings Group.
    """
    deposit_amount: int
    base_charge_amount: int
    mtn_deposit_fee: int
    microbond_deposit_fee: int
    hidden_payout_fee: int
    final_charge_amount: int
    is_fee_milestone: bool
    milestone_triggered_now: bool

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable representation for API response / audit logging."""
        return {
            "deposit_amount": self.deposit_amount,
            "base_charge_amount": self.base_charge_amount,
            "mtn_deposit_fee": self.mtn_deposit_fee,
            "microbond_deposit_fee": self.microbond_deposit_fee,
            "hidden_payout_fee": self.hidden_payout_fee,
            "final_charge_amount": self.final_charge_amount,
            "is_fee_milestone": self.is_fee_milestone,
        }
