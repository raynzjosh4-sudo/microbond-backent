from datetime import datetime, timezone

def now_utc_datetime() -> datetime:
    """Returns current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)
