"""Member metrics. All pure functions of an AnalyticsContext; each returns one value per bucket."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from app.services.analytics.context import AnalyticsContext, Member

_NEVER_MEMBER_STATUSES = {"REJECTED", "DECLINED"}
_INACTIVE_STATUSES = {"LEFT", "REMOVED", "KICKED", "BANNED"}


def was_member(m: Member) -> bool:
    """False for pending/rejected join requests, which never joined the roster."""
    status = (m.status or "").upper()
    return not status.startswith("PENDING") and status not in _NEVER_MEMBER_STATUSES


def effective_left_at(m: Member) -> Optional[int]:
    # An inactive status with no left_at gives us no leave time; treat as left when they joined
    # rather than letting them count as active forever.
    if m.left_at is None and (m.status or "").upper() in _INACTIVE_STATUSES:
        return m.joined_at
    return m.left_at


def active_members(ctx: AnalyticsContext) -> List[Optional[float]]:
    """Members on the roster at the end of each bucket (clipped to 'now' for the current bucket)."""
    roster: List[Tuple[int, Optional[int]]] = [
        (m.joined_at, effective_left_at(m)) for m in ctx.members if was_member(m)
    ]
    out: List[Optional[float]] = []
    for b in ctx.plan.buckets:
        t = min(b.end_ms - 1, ctx.now_ms)
        out.append(float(sum(1 for j, l in roster if j <= t and (l is None or l > t))))
    return out


def new_members(ctx: AnalyticsContext) -> List[Optional[float]]:
    out = [0.0] * len(ctx.plan)
    for m in ctx.members:
        if was_member(m):
            i = ctx.plan.index_of(m.joined_at)
            if i is not None:
                out[i] += 1
    return out


def members_left(ctx: AnalyticsContext) -> List[Optional[float]]:
    out = [0.0] * len(ctx.plan)
    for m in ctx.members:
        if was_member(m):
            i = ctx.plan.index_of(effective_left_at(m))
            if i is not None:
                out[i] += 1
    return out


def _balance_sweep(ctx: AnalyticsContext) -> Dict[str, List[float]]:
    """
    Net balance owed per member over time: (sum of obligations due so far) - (sum of settled deposits).
    Sweeps every due/deposit event once, in time order, tracking members whose balance crosses 0.

      with_balance: members owing money at the end of each bucket
      cleared:      owing -> not owing during the bucket
      new:          not owing -> owing during the bucket
    """
    if "balance" in ctx.memo:
        return ctx.memo["balance"]

    events: List[Tuple[int, int, str]] = [
        (ob.due_date, ob.amount_due, ob.user_id) for ob in ctx.obligations
    ]
    events += [(d.settled_at, -d.amount, d.user_id) for d in ctx.deposits if d.user_id]
    events = [e for e in events if e[0] <= ctx.now_ms]  # future dues are not owed yet
    events.sort(key=lambda e: (e[0], e[1]))  # deposits (negative) before dues at the same instant

    plan = ctx.plan
    n = len(plan)
    with_balance, cleared, new = [0.0] * n, [0.0] * n, [0.0] * n
    balance: Dict[str, int] = defaultdict(int)
    positive, pos = 0, 0
    for k, b in enumerate(plan.buckets):
        while pos < len(events) and events[pos][0] < b.end_ms:
            ts, delta, uid = events[pos]
            before = balance[uid]
            after = before + delta
            balance[uid] = after
            if before <= 0 < after:
                positive += 1
                if ts >= b.start_ms:
                    new[k] += 1
            elif before > 0 >= after:
                positive -= 1
                if ts >= b.start_ms:
                    cleared[k] += 1
            pos += 1
        with_balance[k] = float(positive)

    ctx.memo["balance"] = {"with_balance": with_balance, "cleared": cleared, "new": new}
    return ctx.memo["balance"]


def members_with_balance(ctx: AnalyticsContext) -> List[Optional[float]]:
    return list(_balance_sweep(ctx)["with_balance"])


def members_cleared_balance(ctx: AnalyticsContext) -> List[Optional[float]]:
    return list(_balance_sweep(ctx)["cleared"])


def members_new_balance(ctx: AnalyticsContext) -> List[Optional[float]]:
    return list(_balance_sweep(ctx)["new"])


def members_paid_out(ctx: AnalyticsContext) -> List[Optional[float]]:
    """Distinct members with a COMPLETED payout in the bucket."""
    seen: List[set] = [set() for _ in range(len(ctx.plan))]
    for p in ctx.payouts:
        if p.status == "COMPLETED":
            i = ctx.plan.index_of(p.payout_date)
            if i is not None:
                seen[i].add(p.user_id)
    return [float(len(s)) for s in seen]
