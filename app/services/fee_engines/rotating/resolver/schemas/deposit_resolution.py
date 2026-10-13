from dataclasses import dataclass
from typing import Optional, Dict, Any

from app.services.fee_engines.rotating.resolver.schemas.deposit_status import DepositStatus
from app.services.fee_engines.rotating.resolver.schemas.payment_type import PaymentType
from app.services.fee_engines.rotating.resolver.schemas.deposit_breakdown import (
    DepositBreakdown,
)


@dataclass(frozen=True)
class DepositResolution:
    """
    The complete, authoritative result of resolving a deposit intent.
    """
    status: DepositStatus
    payment_type: PaymentType
    rejection_reason: Optional[str]
    breakdown: Optional[DepositBreakdown]
    final_charge_amount: int
    display_summary: str

    @property
    def is_approved(self) -> bool:
        return self.status != DepositStatus.REJECTED

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable for the deposit-quote API response."""
        result = {
            "status": self.status.value,
            "payment_type": self.payment_type.value,
            "rejection_reason": self.rejection_reason,
            "final_charge_amount": self.final_charge_amount,
            "display_summary": self.display_summary,
        }
        if self.breakdown:
            result["breakdown"] = {
                "current_cycle_due": self.breakdown.current_cycle_due,
                "amount_already_paid": self.breakdown.amount_already_paid,
                "current_cycle_remaining": self.breakdown.current_cycle_remaining,
                "arrears_owed": self.breakdown.arrears_owed,
                "penalties_owed": self.breakdown.penalties_owed,
                "total_outstanding": self.breakdown.total_outstanding,
                "entered_amount": self.breakdown.entered_amount,
                "amount_to_credit": self.breakdown.amount_to_credit,
                "surplus_credited_forward": self.breakdown.surplus_credited_forward,
                "shortfall_remaining": self.breakdown.shortfall_remaining,
                "mtn_collection_fee": self.breakdown.mtn_collection_fee,
                "microbond_base_fee": self.breakdown.microbond_base_fee,
                "milestone_payout_fee": self.breakdown.milestone_payout_fee,
                "total_fee": self.breakdown.total_fee,
                "final_charge_amount": self.breakdown.final_charge_amount,
                "is_milestone_deposit": self.breakdown.is_milestone_deposit,
            }
        return result
