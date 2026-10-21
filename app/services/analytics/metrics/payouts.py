"""Payout metrics. Payouts are pre-scheduled when a group starts, so future rows exist."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services.analytics.buckets import to_local
from app.services.analytics.context import AnalyticsContext

PENDING_STATUSES = {"PENDING", "PROCESSING", "ON_HOLD"}


def payouts_completed(ctx: AnalyticsContext) -> List[Optional[float]]:
    out = [0.0] * len(ctx.plan)
    for p in ctx.payouts:
        if p.status == "COMPLETED":
            i = ctx.plan.index_of(p.payout_date)
            if i is not None:
                out[i] += 1
    return out


def payouts_pending(ctx: AnalyticsContext) -> List[Optional[float]]:
    """Payouts scheduled in the bucket that have not completed yet."""
    out = [0.0] * len(ctx.plan)
    for p in ctx.payouts:
        if p.status in PENDING_STATUSES:
            i = ctx.plan.index_of(p.payout_date)
            if i is not None:
                out[i] += 1
    return out


def payout_progress(ctx: AnalyticsContext) -> List[Optional[float]]:
    """% of scheduled (non-failed) payouts completed by the end of each bucket."""
    total = sum(1 for p in ctx.payouts if p.status != "FAILED")
    completed_dates = sorted(p.payout_date for p in ctx.payouts if p.status == "COMPLETED")
    out: List[Optional[float]] = []
    pos = 0
    for b in ctx.plan.buckets:
        while pos < len(completed_dates) and completed_dates[pos] < b.end_ms:
            pos += 1
        out.append(min(100.0, pos / total * 100.0) if total else 0.0)
    return out


def next_payout_date(ctx: AnalyticsContext) -> Optional[Dict[str, Any]]:
    """Snapshot (not a series): the earliest upcoming unpaid payout, or None."""
    upcoming = [p.payout_date for p in ctx.payouts
                if p.status in PENDING_STATUSES and p.payout_date >= ctx.now_ms]
    if not upcoming:
        return None
    ts = min(upcoming)
    return {"value": ts, "label": to_local(ts).strftime("%d %b %Y")}
