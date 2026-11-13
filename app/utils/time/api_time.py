from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def require_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Datetime must include a timezone.")
    return value.astimezone(timezone.utc)


def local_datetime(day: date, clock: time, timezone_name: str) -> datetime:
    if clock.tzinfo is not None:
        raise ValueError("Local scheduled time must not contain a timezone.")
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown IANA timezone: {timezone_name}") from exc
    return datetime.combine(day, clock, tzinfo=zone).astimezone(timezone.utc)
