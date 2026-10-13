import time
from typing import Optional


def format_last_seen(last_seen_ms: Optional[int], is_online: bool) -> str:
    """Produces human-readable last seen strings (e.g., 'Online', 'Active 5m ago', 'Active 2h ago')."""
    if is_online:
        return "Online"
    if not last_seen_ms:
        return "Offline"

    diff_sec = max(0, int((time.time() * 1000 - last_seen_ms) / 1000))
    if diff_sec < 60:
        return "Active just now"
    elif diff_sec < 3600:
        mins = diff_sec // 60
        return f"Active {mins}m ago"
    elif diff_sec < 86400:
        hours = diff_sec // 3600
        return f"Active {hours}h ago"
    else:
        days = diff_sec // 86400
        return f"Active {days}d ago"
