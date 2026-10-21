"""
Time-bucketing for the Chart Builder.

Turns "last N days" (or an explicit start/end) plus a bucket size into an
ordered list of contiguous buckets that cover the range with no gaps, so charts
never skip empty periods.

Day boundaries use a fixed UTC+3 offset (Africa/Kampala observes no DST), which
avoids a tzdata dependency on Windows.
"""
from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

DAY_MS = 86_400_000
LOCAL_TZ = timezone(timedelta(hours=3), name="EAT")
TIMEZONE_NAME = "Africa/Kampala (UTC+03:00)"

DEFAULT_RANGE_DAYS = 30
MAX_RANGE_DAYS = 730
MAX_BUCKETS = 750
AUTO_TARGET_POINTS = 30
CALENDAR_UNITS = ("month", "year")


class BucketError(ValueError):
    """Raised for invalid range / bucket parameters (maps to HTTP 400)."""


@dataclass(frozen=True)
class Bucket:
    index: int
    start_ms: int   # inclusive
    end_ms: int     # exclusive
    label: str      # full label, e.g. "12 Oct - 15 Oct"
    x_label: str    # short axis tick, e.g. "12 Oct"


@dataclass
class BucketPlan:
    start_ms: int
    end_ms: int
    bucket_days: Optional[int]
    calendar_bucket: Optional[str]
    buckets: Tuple[Bucket, ...]
    _starts: List[int] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._starts = [b.start_ms for b in self.buckets]

    def __len__(self) -> int:
        return len(self.buckets)

    def index_of(self, ts_ms: Optional[int]) -> Optional[int]:
        """Index of the bucket containing ts_ms, or None if outside the range."""
        if ts_ms is None or ts_ms < self.start_ms or ts_ms >= self.end_ms:
            return None
        return bisect_right(self._starts, ts_ms) - 1


def to_local(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000.0, tz=LOCAL_TZ)


def _ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


def local_midnight_ms(ms: int) -> int:
    return _ms(to_local(ms).replace(hour=0, minute=0, second=0, microsecond=0))


def resolve_range(
    now_ms: int,
    days: Optional[int] = None,
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
) -> Tuple[int, int]:
    """Return (start_ms inclusive, end_ms exclusive)."""
    if (start_ms is None) != (end_ms is None):
        raise BucketError("start_ms and end_ms must be provided together.")

    if start_ms is not None:
        if days is not None:
            raise BucketError("Provide either 'days' or 'start_ms'/'end_ms', not both.")
        if end_ms <= start_ms:
            raise BucketError("end_ms must be greater than start_ms.")
    else:
        days = DEFAULT_RANGE_DAYS if days is None else days
        if days < 1:
            raise BucketError("days must be at least 1.")
        # The range ends at the end of today (local), so "last 38 days" = 38 local days incl. today.
        end_ms = local_midnight_ms(now_ms) + DAY_MS
        start_ms = end_ms - days * DAY_MS

    if math.ceil((end_ms - start_ms) / DAY_MS) > MAX_RANGE_DAYS:
        raise BucketError(f"Range too large. Maximum is {MAX_RANGE_DAYS} days.")
    return start_ms, end_ms


def _calendar_bounds(start_ms: int, end_ms: int, unit: str) -> List[Tuple[int, int]]:
    bounds: List[Tuple[int, int]] = []
    cur = start_ms
    while cur < end_ms:
        dt = to_local(cur)
        if unit == "month":
            first = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            nxt_dt = (first + timedelta(days=32)).replace(day=1)
        else:
            nxt_dt = dt.replace(year=dt.year + 1, month=1, day=1,
                                hour=0, minute=0, second=0, microsecond=0)
        nxt = _ms(nxt_dt)
        bounds.append((cur, min(nxt, end_ms)))
        cur = nxt
    return bounds


def _labels(start_ms: int, end_ms: int, calendar_bucket: Optional[str]) -> Tuple[str, str]:
    s = to_local(start_ms)
    e = to_local(end_ms - 1)
    if calendar_bucket == "month":
        text = s.strftime("%b %Y")
        return text, text
    if calendar_bucket == "year":
        text = s.strftime("%Y")
        return text, text
    short = s.strftime("%d %b")
    if s.date() == e.date():
        return short, short
    return f"{short} - {e.strftime('%d %b')}", short


def build_plan(
    now_ms: int,
    days: Optional[int] = None,
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
    bucket_days: Optional[int] = None,
    calendar_bucket: Optional[str] = None,
) -> BucketPlan:
    start_ms, end_ms = resolve_range(now_ms, days, start_ms, end_ms)
    span_days = math.ceil((end_ms - start_ms) / DAY_MS)

    if calendar_bucket is not None:
        if calendar_bucket not in CALENDAR_UNITS:
            raise BucketError("calendar_bucket must be 'month' or 'year'.")
        bounds = _calendar_bounds(start_ms, end_ms, calendar_bucket)
        bucket_days = None
    else:
        if bucket_days is None:
            bucket_days = max(1, math.ceil(span_days / AUTO_TARGET_POINTS))
        if bucket_days < 1:
            raise BucketError("bucket_days must be at least 1.")
        size = bucket_days * DAY_MS
        bounds = [(s, min(s + size, end_ms)) for s in range(start_ms, end_ms, size)]

    if len(bounds) > MAX_BUCKETS:
        raise BucketError(
            f"Too many buckets ({len(bounds)}). Maximum is {MAX_BUCKETS}; use a larger bucket size."
        )

    buckets = []
    for i, (s, e) in enumerate(bounds):
        label, x_label = _labels(s, e, calendar_bucket)
        buckets.append(Bucket(index=i, start_ms=s, end_ms=e, label=label, x_label=x_label))

    return BucketPlan(
        start_ms=start_ms,
        end_ms=end_ms,
        bucket_days=bucket_days,
        calendar_bucket=calendar_bucket,
        buckets=tuple(buckets),
    )
