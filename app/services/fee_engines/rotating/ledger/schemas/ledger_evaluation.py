from dataclasses import dataclass
from typing import Dict, Any
from app.services.fee_engines.rotating.ledger.schemas.ledger_status import LedgerStatus


@dataclass(frozen=True)
class LedgerEvaluation:
    """
    The complete ledger snapshot for a single member at the moment of evaluation.
    """
    status: LedgerStatus
    expected_balance_today: int
    actual_paid_balance: int
    net_balance: int
    catch_up_amount: int
    days_ahead: int
    days_in_arrears: int
    should_send_reminder: bool
    unpaid_penalties_ugx: int
    days_elapsed: int
    periods_elapsed: float
    expected_periods_paid: int

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serializable for deposit-info API response and cron logs."""
        return {
            "status": self.status.value,
            "expected_balance_today": self.expected_balance_today,
            "actual_paid_balance": self.actual_paid_balance,
            "net_balance": self.net_balance,
            "catch_up_amount": self.catch_up_amount,
            "days_ahead": self.days_ahead,
            "days_in_arrears": self.days_in_arrears,
            "should_send_reminder": self.should_send_reminder,
            "unpaid_penalties_ugx": self.unpaid_penalties_ugx,
            "days_elapsed": self.days_elapsed,
            "periods_elapsed": round(self.periods_elapsed, 2),
            "expected_periods_paid": self.expected_periods_paid,
        }

    @property
    def dashboard_color(self) -> str:
        """Flutter dashboard card color token driven by ledger status."""
        return {
            LedgerStatus.AHEAD:    "GREEN",
            LedgerStatus.ON_TRACK: "BLUE",
            LedgerStatus.BEHIND:   "RED",
        }[self.status]

    @property
    def dashboard_label(self) -> str:
        """Short label for the mobile dashboard card."""
        if self.status == LedgerStatus.AHEAD:
            return f"Paid ahead — {self.days_ahead} day(s) covered"
        if self.status == LedgerStatus.ON_TRACK:
            return "On track"
        return f"Arrears: {self.catch_up_amount:,} UGX"
