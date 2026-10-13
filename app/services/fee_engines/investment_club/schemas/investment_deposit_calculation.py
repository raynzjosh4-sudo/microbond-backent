from dataclasses import dataclass
from typing import Dict, List, Any

# MTN MoMo flat fee charged per disbursement (bulk Share Out payout)
MTN_FLAT_PAYOUT_FEE: int = 300  # UGX

# Microbond platform profit per member per annual payout
MICROBOND_PAYOUT_PROFIT: int = 679  # UGX

# Total cost recovered per member per accounting year
TARGET_PAYOUT_FEE: int = MTN_FLAT_PAYOUT_FEE + MICROBOND_PAYOUT_PROFIT  # 979 UGX

# The three deposit-count milestones within an accounting year:
DEPOSIT_COUNT_MILESTONES: List[int] = [1, 4, 8]

# Human-readable labels for logging / audit
MILESTONE_LABEL: Dict[int, str] = {
    1: "EARLY_1ST",
    4: "MID_4TH",
    8: "LATE_8TH",
}


@dataclass(frozen=True)
class InvestmentDepositCalculation:
    """
    Immutable result of a single deposit calculation in an Investment Club.
    """
    deposit_amount: int
    base_charge_amount: int
    mtn_deposit_fee: int
    microbond_deposit_fee: int
    hidden_payout_fee: int
    final_charge_amount: int
    is_fee_milestone: bool
    this_deposit_number: int

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
            "this_deposit_number": self.this_deposit_number,
        }
