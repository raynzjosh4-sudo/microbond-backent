from app.models.group.ledger.ledger_entry import LedgerEntry
from app.utils.time.now_epoch_ms import now_epoch_ms

utc_now = now_epoch_ms

__all__ = ["LedgerEntry", "utc_now"]
