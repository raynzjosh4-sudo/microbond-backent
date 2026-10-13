from dataclasses import dataclass
from typing import Dict, Any

# MTN MoMo flat fee charged per emergency disbursement
MTN_FLAT_PAYOUT_FEE: int = 300  # UGX

# Microbond platform profit per disbursement event
MICROBOND_PAYOUT_PROFIT: int = 679  # UGX

# Total cost recovered per emergency payout event
TARGET_PAYOUT_FEE: int = MTN_FLAT_PAYOUT_FEE + MICROBOND_PAYOUT_PROFIT  # 979 UGX


@dataclass(frozen=True)
class EmergencyDepositCalculation:
    """
    Immutable result of a single deposit calculation for an Emergency /
    Welfare Fund group.
    """
    deposit_amount: int
    base_charge_amount: int
    mtn_deposit_fee: int
    microbond_deposit_fee: int
    hidden_payout_fee: int
    final_charge_amount: int
    cleared_pending_fee: bool
    fees_cleared: int

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable representation for API response / audit logging."""
        return {
            "deposit_amount": self.deposit_amount,
            "base_charge_amount": self.base_charge_amount,
            "mtn_deposit_fee": self.mtn_deposit_fee,
            "microbond_deposit_fee": self.microbond_deposit_fee,
            "hidden_payout_fee": self.hidden_payout_fee,
            "final_charge_amount": self.final_charge_amount,
            "cleared_pending_fee": self.cleared_pending_fee,
            "fees_cleared": self.fees_cleared,
        }
