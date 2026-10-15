from datetime import datetime, timezone

def utc_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)
