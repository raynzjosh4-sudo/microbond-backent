from datetime import datetime, timezone
from typing import Optional

from app.services.fee_engines.rotating.ledger.schemas.ledger_status import LedgerStatus
from app.services.fee_engines.rotating.ledger.schemas.ledger_evaluation import (
    LedgerEvaluation,
)


def evaluate_member_ledger(
    contribution_amount: int,
    collection_frequency_days: int,
    group_start_time_ms: int,
    actual_paid_balance: int,
    unpaid_penalties_ugx: int = 0,
    current_time_ms: Optional[int] = None,
    effective_start_time_ms: Optional[int] = None,
) -> LedgerEvaluation:
    """
    Evaluate a member's payment standing in a Rotating Group using the
    ledger model: expected balance vs actual paid balance.
    """
    if not isinstance(contribution_amount, int) or contribution_amount <= 0:
        raise ValueError(f"contribution_amount must be a positive int. Got: {contribution_amount!r}")
    if not isinstance(collection_frequency_days, int) or collection_frequency_days <= 0:
        raise ValueError(f"collection_frequency_days must be a positive int. Got: {collection_frequency_days!r}")

    now_ms = current_time_ms if current_time_ms is not None else int(
        datetime.now(timezone.utc).timestamp() * 1000
    )
    obligation_start_ms = effective_start_time_ms if effective_start_time_ms is not None else group_start_time_ms
    elapsed_ms = max(0, now_ms - obligation_start_ms)
    days_elapsed = elapsed_ms // 86_400_000

    periods_elapsed = days_elapsed / collection_frequency_days
    expected_periods = int(periods_elapsed)

    expected_balance = expected_periods * contribution_amount
    net_balance = actual_paid_balance - expected_balance

    if net_balance > 0:
        days_ahead = int(net_balance // contribution_amount) * collection_frequency_days
        days_in_arrears = 0
        catch_up_amount = 0
        status = LedgerStatus.AHEAD
        should_remind = False

    elif net_balance == 0:
        days_ahead = 0
        days_in_arrears = 0
        catch_up_amount = unpaid_penalties_ugx
        status = LedgerStatus.ON_TRACK
        should_remind = False

    else:
        arrears_ugx = abs(net_balance)
        days_in_arrears = int(arrears_ugx // contribution_amount) * collection_frequency_days
        days_ahead = 0
        catch_up_amount = arrears_ugx + unpaid_penalties_ugx
        status = LedgerStatus.BEHIND
        should_remind = True

    return LedgerEvaluation(
        status=status,
        expected_balance_today=expected_balance,
        actual_paid_balance=actual_paid_balance,
        net_balance=net_balance,
        catch_up_amount=catch_up_amount,
        days_ahead=days_ahead,
        days_in_arrears=days_in_arrears,
        should_send_reminder=should_remind,
        unpaid_penalties_ugx=unpaid_penalties_ugx,
        days_elapsed=int(days_elapsed),
        periods_elapsed=periods_elapsed,
        expected_periods_paid=expected_periods,
    )
