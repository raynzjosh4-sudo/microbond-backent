"""Unit tests for the Chart Builder bucketing engine (no database required)."""
from datetime import datetime, timezone

import pytest

from app.services.analytics.buckets import (
    DAY_MS,
    LOCAL_TZ,
    BucketError,
    build_plan,
    to_local,
)


def ms(y, m, d, h=0, mi=0):
    return int(datetime(y, m, d, h, mi, tzinfo=LOCAL_TZ).timestamp() * 1000)


NOW = ms(2026, 10, 21, 12)  # Wed 21 Oct 2026, noon EAT


def assert_contiguous(plan):
    assert plan.buckets[0].start_ms == plan.start_ms
    assert plan.buckets[-1].end_ms == plan.end_ms
    for a, b in zip(plan.buckets, plan.buckets[1:]):
        assert a.end_ms == b.start_ms


def test_any_number_of_days_daily_buckets():
    plan = build_plan(NOW, days=38, bucket_days=1)
    assert len(plan) == 38
    assert plan.end_ms == ms(2026, 10, 22)           # end of today (local)
    assert plan.start_ms == plan.end_ms - 38 * DAY_MS
    assert_contiguous(plan)
    assert plan.buckets[-1].x_label == "21 Oct"


def test_four_days_single_bucket():
    plan = build_plan(NOW, days=4, bucket_days=4)
    assert len(plan) == 1
    assert plan.buckets[0].label == "18 Oct - 21 Oct"


def test_bucket_size_does_not_divide_range_last_bucket_is_clipped():
    plan = build_plan(NOW, days=38, bucket_days=7)
    assert len(plan) == 6                              # 5 full + a 3-day tail
    assert plan.buckets[-1].end_ms - plan.buckets[-1].start_ms == 3 * DAY_MS
    assert_contiguous(plan)


def test_custom_bucket_larger_than_range_gives_one_bucket():
    assert len(build_plan(NOW, days=5, bucket_days=30)) == 1


def test_auto_bucket_targets_about_thirty_points():
    plan = build_plan(NOW, days=90)
    assert plan.bucket_days == 3
    assert len(plan) == 30


def test_default_range_is_30_days():
    plan = build_plan(NOW)
    assert plan.end_ms - plan.start_ms == 30 * DAY_MS


def test_calendar_month_buckets_clip_first_and_last():
    plan = build_plan(NOW, days=60, calendar_bucket="month")
    assert [b.label for b in plan.buckets] == ["Aug 2026", "Sep 2026", "Oct 2026"]
    assert plan.bucket_days is None
    assert_contiguous(plan)
    assert plan.buckets[1].start_ms == ms(2026, 9, 1)


def test_calendar_year_buckets_cross_new_year():
    plan = build_plan(ms(2026, 1, 10, 12), days=30, calendar_bucket="year")
    assert [b.label for b in plan.buckets] == ["2025", "2026"]


def test_explicit_start_end_range():
    plan = build_plan(NOW, start_ms=ms(2026, 10, 1), end_ms=ms(2026, 10, 11), bucket_days=5)
    assert len(plan) == 2
    assert plan.start_ms == ms(2026, 10, 1)


def test_index_of_boundaries():
    plan = build_plan(NOW, days=4, bucket_days=1)
    assert plan.index_of(plan.start_ms) == 0
    assert plan.index_of(plan.buckets[1].start_ms) == 1
    assert plan.index_of(plan.buckets[1].start_ms - 1) == 0
    assert plan.index_of(plan.end_ms - 1) == 3
    assert plan.index_of(plan.end_ms) is None
    assert plan.index_of(plan.start_ms - 1) is None
    assert plan.index_of(None) is None


def test_day_boundary_uses_local_time_not_utc():
    # 22:30 UTC on the 20th is 01:30 EAT on the 21st -> belongs to the 21 Oct bucket.
    plan = build_plan(NOW, days=2, bucket_days=1)
    ts = int(datetime(2026, 10, 20, 22, 30, tzinfo=timezone.utc).timestamp() * 1000)
    assert plan.buckets[plan.index_of(ts)].x_label == "21 Oct"
    assert to_local(ts).day == 21


@pytest.mark.parametrize("kwargs", [
    {"days": 0},
    {"days": 731},
    {"days": 10, "bucket_days": 0},
    {"days": 10, "start_ms": 1, "end_ms": 2},
    {"start_ms": 1000},
    {"start_ms": 2000, "end_ms": 1000},
    {"days": 10, "calendar_bucket": "week"},
])
def test_invalid_parameters_raise(kwargs):
    with pytest.raises(BucketError):
        build_plan(NOW, **kwargs)
