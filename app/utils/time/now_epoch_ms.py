from datetime import datetime, timezone

def now_epoch_ms() -> int:
    """Returns current UTC timestamp in milliseconds (integer)."""
    return int(datetime.now(timezone.utc).timestamp() * 1000)

# Backward-compatible alias
utc_now = now_epoch_ms
