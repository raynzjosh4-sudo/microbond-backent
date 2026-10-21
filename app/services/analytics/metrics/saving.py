"""Saving metrics. All pure functions of an AnalyticsContext; each returns one value per bucket."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional

from app.services.analytics.buckets import to_local
from app.services.analytics.context import AnalyticsContext
from app.services.analytics.metrics.members import effective_left_at, was_member

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _zeros(ctx: AnalyticsContext) -> List[float]:
    return [0.0] * len(ctx.plan)


def _deposit_sums_and_counts(ctx: AnalyticsContext):
    if "deposit_buckets" not in ctx.memo:
        sums, counts = _zeros(ctx), _zeros(ctx)
        for d in ctx.deposits:
            i = ctx.plan.index_of(d.settled_at)
            if i is not None:
                sums[i] += d.amount
                counts[i] += 1
        ctx.memo["deposit_buckets"] = (sums, counts)
    return ctx.memo["deposit_buckets"]


def daily_saving(ctx: AnalyticsContext) -> List[Optional[float]]:
    """Money actually deposited (settled ledger deposits) per bucket."""
    return list(_deposit_sums_and_counts(ctx)[0])


def average_deposit_size(ctx: AnalyticsContext) -> List[Optional[float]]:
    sums, counts = _deposit_sums_and_counts(ctx)
    return [s / c if c else 0.0 for s, c in zip(sums, counts)]


def total_accumulation(ctx: AnalyticsContext) -> List[Optional[float]]:
    """Total saved to date: cumulative deposits, starting from everything saved before the range."""
    running = float(sum(d.amount for d in ctx.deposits if d.settled_at < ctx.plan.start_ms))
    sums, _ = _deposit_sums_and_counts(ctx)
    out: List[Optional[float]] = []
    for s in sums:
        running += s
        out.append(running)
    return out


def period_change(ctx: AnalyticsContext) -> List[Optional[float]]:
    """
    % change in deposits vs the previous bucket (a week-over-week change when buckets are 7 days).
    The first bucket is compared against a window of the same length immediately before the range.
    A rise from zero is reported as +100%.
    """
    sums, _ = _deposit_sums_and_counts(ctx)
    first = ctx.plan.buckets[0]
    length = first.end_ms - first.start_ms
    prev_first = float(sum(
        d.amount for d in ctx.deposits
        if ctx.plan.start_ms - length <= d.settled_at < ctx.plan.start_ms
    ))
    out: List[Optional[float]] = []
    prev = prev_first
    for cur in sums:
        if prev > 0:
            out.append((cur - prev) / prev * 100.0)
        else:
            out.append(0.0 if cur == 0 else 100.0)
        prev = cur
    return out


# ── Save-day metrics (one obligation = one save-day) ──────────────────────

def _save_day_counts(ctx: AnalyticsContext) -> Dict[str, List[float]]:
    """
    successful: paid > 0.  full: paid >= due.  partial: 0 < paid < due.
    none: paid == 0 AND already due (future obligations are not "missed").
    """
    if "save_days" not in ctx.memo:
        out = {k: _zeros(ctx) for k in ("successful", "full", "partial", "none", "due")}
        for ob in ctx.obligations:
            i = ctx.plan.index_of(ob.due_date)
            if i is None:
                continue
            out["due"][i] += 1
            if ob.amount_paid > 0:
                out["successful"][i] += 1
                if ob.amount_paid >= ob.amount_due:
                    out["full"][i] += 1
                else:
                    out["partial"][i] += 1
            elif ob.due_date < ctx.now_ms:
                out["none"][i] += 1
        ctx.memo["save_days"] = out
    return ctx.memo["save_days"]


def successful_save_days(ctx): return list(_save_day_counts(ctx)["successful"])
def full_save_days(ctx): return list(_save_day_counts(ctx)["full"])
def partial_save_days(ctx): return list(_save_day_counts(ctx)["partial"])
def no_save_days(ctx): return list(_save_day_counts(ctx)["none"])
def obligations_due(ctx): return list(_save_day_counts(ctx)["due"])


def _rate(numerator: List[float], denominator: List[float]) -> List[Optional[float]]:
    return [n / d * 100.0 if d else 0.0 for n, d in zip(numerator, denominator)]


def missed_saving_rate(ctx: AnalyticsContext) -> List[Optional[float]]:
    c = _save_day_counts(ctx)
    considered = [s + n for s, n in zip(c["successful"], c["none"])]
    return _rate(c["none"], considered)


def target_met_rate(ctx: AnalyticsContext) -> List[Optional[float]]:
    c = _save_day_counts(ctx)
    considered = [s + n for s, n in zip(c["successful"], c["none"])]
    return _rate(c["full"], considered)


def average_saving_streak(ctx: AnalyticsContext) -> List[Optional[float]]:
    """
    Per member: consecutive successful save-days ending at the bucket end (a miss resets it).
    Only resolved obligations count (already due, or paid in advance). Averaged over members
    with at least one resolved obligation by that point.
    """
    by_user: Dict[str, list] = defaultdict(list)
    for ob in ctx.obligations:
        if ob.due_date < ctx.now_ms or ob.amount_paid > 0:
            by_user[ob.user_id].append(ob)

    plan = ctx.plan
    totals = [0.0] * len(plan)
    counted = [0] * len(plan)
    for obs in by_user.values():
        obs.sort(key=lambda o: o.due_date)
        pos, streak, seen = 0, 0, False
        for k, b in enumerate(plan.buckets):
            while pos < len(obs) and obs[pos].due_date < b.end_ms:
                streak = streak + 1 if obs[pos].amount_paid > 0 else 0
                seen = True
                pos += 1
            if seen:
                totals[k] += streak
                counted[k] += 1
    return [t / c if c else 0.0 for t, c in zip(totals, counted)]


# ── Activity ─────────────────────────────────────────────────────────────

def weekday_deposit_counts(ctx: AnalyticsContext) -> List[List[int]]:
    """For each bucket, deposit counts per weekday (Mon=0)."""
    out = [[0] * 7 for _ in range(len(ctx.plan))]
    for d in ctx.deposits:
        i = ctx.plan.index_of(d.settled_at)
        if i is not None:
            out[i][to_local(d.settled_at).weekday()] += 1
    return out


def busiest_saving_day(ctx: AnalyticsContext) -> List[Optional[float]]:
    """Weekday index (Mon=0..Sun=6) with the most deposits in each bucket; None if no deposits."""
    out: List[Optional[float]] = []
    for counts in weekday_deposit_counts(ctx):
        out.append(float(counts.index(max(counts))) if any(counts) else None)
    return out


def total_group_activity(ctx: AnalyticsContext) -> List[Optional[float]]:
    """Deposits + completed payouts + joins + leaves + chat messages."""
    out = _zeros(ctx)
    _, deposit_counts = _deposit_sums_and_counts(ctx)
    for i, c in enumerate(deposit_counts):
        out[i] += c
    for p in ctx.payouts:
        if p.status == "COMPLETED":
            i = ctx.plan.index_of(p.payout_date)
            if i is not None:
                out[i] += 1
    for m in ctx.members:
        if not was_member(m):
            continue
        for ts in (m.joined_at, effective_left_at(m)):
            i = ctx.plan.index_of(ts)
            if i is not None:
                out[i] += 1
    for ts in ctx.chat_times:
        i = ctx.plan.index_of(ts)
        if i is not None:
            out[i] += 1
    return out
