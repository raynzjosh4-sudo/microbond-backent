from dataclasses import dataclass
from typing import Dict, Any

# MTN MoMo flat fee charged per disbursement (transfer-to-mobile)
MTN_FLAT_PAYOUT_FEE: int = 300  # UGX

# Microbond profit margin retained per payout
MICROBOND_PAYOUT_PROFIT: int = 679  # UGX

# Total cost the platform must recover per payout event
TARGET_PAYOUT_FEE: int = MTN_FLAT_PAYOUT_FEE + MICROBOND_PAYOUT_PROFIT  # 979 UGX

# Milestone labels for clarity and logging
MILESTONE_START = "START"
MILESTONE_MIDDLE = "MIDDLE"
MILESTONE_LAST = "LAST"


@dataclass(frozen=True)
class MemberDepositSchedule:
    """
    The complete deposit instruction set for a single group member for the
    full cycle. Generated once at group creation and stored in the database.
    """
    member_index: int
    total_rounds: int
    group_target_amount: int
    base_charge_amount: int
    milestone_round_number: int
    milestone_type: str
    milestone_charge_amount: int
    hidden_payout_fee: int
    mtn_deposit_fee: int
    microbond_deposit_fee: int

    def charge_for_round(self, round_number: int) -> int:
        """Return the exact charge amount for a given 1-based round number."""
        if round_number == self.milestone_round_number:
            return self.milestone_charge_amount
        return self.base_charge_amount

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable representation for database storage."""
        return {
            "member_index": self.member_index,
            "total_rounds": self.total_rounds,
            "group_target_amount": self.group_target_amount,
            "base_charge_amount": self.base_charge_amount,
            "milestone_round_number": self.milestone_round_number,
            "milestone_type": self.milestone_type,
            "milestone_charge_amount": self.milestone_charge_amount,
            "hidden_payout_fee": self.hidden_payout_fee,
            "mtn_deposit_fee": self.mtn_deposit_fee,
            "microbond_deposit_fee": self.microbond_deposit_fee,
        }
