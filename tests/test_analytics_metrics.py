"""
Unit tests for Chart Builder metrics, using in-memory rows (no database).

Scenario (EAT, "now" = Wed 21 Oct 2026 12:00, range = 18-21 Oct, 1-day buckets):
  Member A: obligations of 100 on 18/19/20 Oct (paid 100 / 50 / 0) and one due 21 Oct 18:00 (future, unpaid)
  Member B: obligations of 100 on 18/19/20 Oct (all paid) and one due 21 Oct 11:00 (past, unpaid)
"""
from datetime import datetime

import pytest

from app.services.analytics.buckets import LOCAL_TZ, build_plan, to_local
from app.services.analytics.context import AnalyticsContext, Deposit, Member, Obligation, Payout
from app.services.analytics.registry import CATALOG_ORDER, REGISTRY, is_available


def ms(y, m, d, h=0, mi=0):
    return int(datetime(y, m, d, h, mi, tzinfo=LOCAL_TZ).timestamp() * 1000)


NOW = ms(2026, 10, 21, 12)
A, B, C = "user-a", "user-b", "user-c"


@pytest.fixture
def ctx():
    plan = build_plan(NOW, days=4, bucket_days=1)
    obligations = [
        Obligation(1, A, ms(2026, 10, 18), 100, 100, "PAID"),
        Obligation(2, A, ms(2026, 10, 19), 100, 50, "LATE"),
        Obligation(3, A, ms(2026, 10, 20), 100, 0, "LATE"),
        Obligation(4, A, ms(2026, 10, 21, 18), 100, 0, "PENDING"),
        Obligation(5, B, ms(2026, 10, 18), 100, 100, "PAID"),
        Obligation(6, B, ms(2026, 10, 19), 100, 100, "PAID"),
        Obligation(7, B, ms(2026, 10, 20), 100, 100, "PAID"),
        Obligation(8, B, ms(2026, 10, 21, 11), 100, 0, "LATE"),
    ]
    deposits = [
        Deposit(C, None, 1000, ms(2026, 10, 10, 9)),        # before the range
        Deposit(A, 1, 100, ms(2026, 10, 18, 10)),
        Deposit(B, 5, 100, ms(2026, 10, 18, 10)),
        Deposit(A, 2, 50, ms(2026, 10, 19, 10)),
        Deposit(B, 6, 100, ms(2026, 10, 19, 10)),
        Deposit(B, 7, 100, ms(2026, 10, 20, 10)),
    ]
    members = [
        Member("m1", "ACTIVE", ms(2026, 10, 10), None),
        Member("m2", "ACTIVE", ms(2026, 10, 19, 12), None),
        Member("m3", "LEFT", ms(2026, 10, 5), ms(2026, 10, 20, 10)),
        Member("m4", "PENDING_APPROVAL", ms(2026, 10, 19), None),
    ]
    payouts = [
        Payout(A, "COMPLETED", ms(2026, 10, 19), 200, 200),
        Payout(B, "COMPLETED", ms(2026, 10, 20), 200, 200),
        Payout(C, "PENDING", ms(2026, 10, 25), 200, 0),
        Payout(C, "FAILED", ms(2026, 10, 1), 200, 0),
    ]
    return AnalyticsContext(plan, NOW, preloaded={
        "obligations": obligations, "deposits": deposits, "members": members,
        "payouts": payouts, "chat_times": [ms(2026, 10, 19, 8), ms(2026, 10, 19, 9)],
    })


def run(ctx, metric_id):
    return REGISTRY[metric_id].compute(ctx)


def test_save_day_counts(ctx):
    assert run(ctx, "successful_save_days") == [2, 2, 1, 0]
    assert run(ctx, "full_save_days") == [2, 1, 1, 0]
    assert run(ctx, "partial_save_days") == [0, 1, 0, 0]
    # A's 21 Oct obligation is still in the future, so only B's counts as missed that day.
    assert run(ctx, "no_save_days") == [0, 0, 1, 1]
    assert run(ctx, "obligations_due") == [2, 2, 2, 2]


def test_rates(ctx):
    assert run(ctx, "missed_saving_rate") == pytest.approx([0, 0, 50, 100])
    assert run(ctx, "target_met_rate") == pytest.approx([100, 50, 50, 0])


def test_average_saving_streak(ctx):
    # A: 1,2,0,0   B: 1,2,3,0   (A's future obligation is unresolved and ignored)
    assert run(ctx, "average_saving_streak") == pytest.approx([1, 2, 1.5, 0])


def test_money_from_ledger(ctx):
    assert run(ctx, "daily_saving") == [200, 150, 100, 0]
    assert run(ctx, "average_deposit_size") == pytest.approx([100, 75, 100, 0])


def test_total_accumulation_starts_from_opening_balance(ctx):
    assert run(ctx, "total_accumulation") == [1200, 1350, 1450, 1450]


def test_period_change(ctx):
    assert run(ctx, "week_over_week_change") == pytest.approx([100, -25, -100 / 3, -100])


def test_busiest_day_is_local_weekday(ctx):
    values = run(ctx, "busiest_saving_day")
    assert values[:3] == [
        float(to_local(ms(2026, 10, d, 10)).weekday()) for d in (18, 19, 20)
    ]
    assert values[3] is None


def test_members(ctx):
    assert run(ctx, "active_members") == [2, 3, 2, 2]       # pending member never counts
    assert run(ctx, "new_members") == [0, 1, 0, 0]
    assert run(ctx, "members_left") == [0, 0, 1, 0]


def test_balance_metrics_and_conservation(ctx):
    with_balance = run(ctx, "members_with_balance")
    new = run(ctx, "members_new_balance")
    cleared = run(ctx, "members_cleared_balance")
    assert with_balance == [0, 1, 1, 2]                      # future-dated due ignored
    assert cleared == [2, 1, 1, 0]
    assert new == [2, 2, 1, 1]
    prev = 0
    for w, n, c in zip(with_balance, new, cleared):          # end = start + new - cleared
        assert w == prev + n - c
        prev = w


def test_payouts(ctx):
    assert run(ctx, "payouts_completed") == [0, 1, 1, 0]
    assert run(ctx, "members_paid_out") == [0, 1, 1, 0]
    assert run(ctx, "payouts_pending") == [0, 0, 0, 0]       # the pending one is 25 Oct, outside range
    assert run(ctx, "payout_progress") == pytest.approx([0, 100 / 3, 200 / 3, 200 / 3])


def test_next_payout_date_snapshot(ctx):
    snap = REGISTRY["next_payout_date"].snapshot(ctx)
    assert snap["value"] == ms(2026, 10, 25)
    assert snap["label"] == "25 Oct 2026"


def test_total_group_activity(ctx):
    # d19: 2 deposits + 1 payout + 1 join (m2) + 2 chat = 6
    assert run(ctx, "total_group_activity")[1] == 6


def test_every_metric_returns_one_value_per_bucket(ctx):
    for metric in REGISTRY.values():
        if metric.compute:
            assert len(metric.compute(ctx)) == len(ctx.plan), metric.id


def test_longer_range_with_empty_buckets_is_zero_filled():
    plan = build_plan(NOW, days=38, bucket_days=1)
    ctx = AnalyticsContext(plan, NOW, preloaded={
        "obligations": [], "deposits": [], "members": [], "payouts": [], "chat_times": [],
    })
    assert run(ctx, "daily_saving") == [0.0] * 38
    assert run(ctx, "total_accumulation") == [0.0] * 38


def test_catalog_is_complete_and_consistent():
    ids = [m.id for m in CATALOG_ORDER]
    assert len(ids) == len(set(ids)) == 22
    assert {m.category for m in CATALOG_ORDER} == {"SAVING", "MEMBERS", "PAYOUTS"}
    for m in CATALOG_ORDER:
        assert (m.compute is None) == (m.snapshot is not None), m.id


class _Vis:
    def __init__(self, **kw):
        self.vis_report_actual_collection = kw.get("collection", False)
        self.vis_manage_payout_order = kw.get("payouts", False)
        self.hide_total_group_balance = kw.get("hide_balance", False)


def test_visibility_gating():
    daily, accum, nxt = REGISTRY["daily_saving"], REGISTRY["total_accumulation"], REGISTRY["next_payout_date"]
    assert is_available(daily, None, is_admin=True)
    assert not is_available(daily, _Vis(), is_admin=False)
    assert is_available(daily, _Vis(collection=True), is_admin=False)
    assert not is_available(accum, _Vis(collection=True, hide_balance=True), is_admin=False)
    assert not is_available(nxt, _Vis(collection=True), is_admin=False)
    assert is_available(nxt, _Vis(payouts=True), is_admin=False)
    assert is_available(REGISTRY["successful_save_days"], None, is_admin=False)  # ungated
