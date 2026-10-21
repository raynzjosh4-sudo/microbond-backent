"""
Real-data replacements for the values that used to be hardcoded in the weekly report
(members joined/left, eligible save-days, balance counts, activity, payout rotation names).

Built on the same metric functions as the Chart Builder so the report card and the charts
can never disagree.
"""
from __future__ import annotations

import math
import uuid
from typing import Any, Dict, List, Optional

from sqlmodel import Session, select

from app.services.analytics.buckets import DAY_MS, build_plan
from app.services.analytics.context import AnalyticsContext
from app.services.analytics.metrics import members as mem
from app.services.analytics.metrics import payouts as pay
from app.services.analytics.metrics import saving as sav

WEEKDAYS = sav.WEEKDAYS


def short_name(full_name: Optional[str]) -> str:
    """'Grace Namukasa' -> 'Grace N.'"""
    parts = (full_name or "").split()
    if not parts:
        return "Member"
    if len(parts) == 1:
        return parts[0]
    return f"{parts[0]} {parts[-1][0].upper()}."


def format_weekdays(indices: List[int]) -> Optional[str]:
    """[3,4,5,6] -> 'Thu-Sun'; [0,4] -> 'Mon, Fri'; [] -> None."""
    if not indices:
        return None
    runs: List[List[int]] = []
    for i in sorted(set(indices)):
        if runs and i == runs[-1][-1] + 1:
            runs[-1].append(i)
        else:
            runs.append([i])
    parts: List[str] = []
    for run in runs:
        if len(run) >= 3:
            parts.append(f"{WEEKDAYS[run[0]]}-{WEEKDAYS[run[-1]]}")
        else:
            parts.extend(WEEKDAYS[i] for i in run)
    return ", ".join(parts)


def _names_for(session: Session, user_ids: List[str]) -> List[str]:
    if not user_ids:
        return []
    from app.models.user.user import User

    uuids = []
    for uid in user_ids:
        try:
            uuids.append(uuid.UUID(uid))
        except ValueError:
            continue
    rows = session.exec(select(User.id, User.full_name).where(User.id.in_(uuids))).all()
    by_id = {str(r[0]): short_name(r[1]) for r in rows}
    return [by_id.get(uid, "Member") for uid in user_ids]


def build_period_summary(
    session: Session,
    group_id: str,
    start_ms: int,
    end_ms_exclusive: int,
    now_ms: int,
) -> Dict[str, Any]:
    span = end_ms_exclusive - start_ms
    plan = build_plan(
        now_ms,
        start_ms=start_ms,
        end_ms=end_ms_exclusive,
        bucket_days=max(1, math.ceil(span / DAY_MS)),  # a single bucket covering the whole period
    )
    ctx = AnalyticsContext(plan, now_ms, session, group_id)

    joined = int(mem.new_members(ctx)[0])
    left = int(mem.members_left(ctx)[0])
    members_now = int(mem.active_members(ctx)[0])

    end_with_balance = int(mem.members_with_balance(ctx)[0])
    new_balances = int(mem.members_new_balance(ctx)[0])
    cleared_balance = int(mem.members_cleared_balance(ctx)[0])

    counts = sav.weekday_deposit_counts(ctx)[0]
    if any(counts):
        busiest_count, quietest_count = max(counts), min(counts)
        busiest = format_weekdays([i for i, c in enumerate(counts) if c == busiest_count])
        quietest = format_weekdays([i for i, c in enumerate(counts) if c == quietest_count])
    else:
        busiest = quietest = None
        busiest_count = quietest_count = 0

    completed = sorted(
        (p for p in ctx.payouts if p.status == "COMPLETED" and start_ms <= p.payout_date < end_ms_exclusive),
        key=lambda p: p.payout_date,
    )
    next_window_end = end_ms_exclusive + span
    upcoming = sorted(
        (p for p in ctx.payouts if p.status in pay.PENDING_STATUSES and p.payout_date >= end_ms_exclusive),
        key=lambda p: p.payout_date,
    )
    next_up = [p for p in upcoming if p.payout_date < next_window_end]
    remaining = len(upcoming) - len(next_up)

    return {
        "members": {
            "start": members_now - joined + left,
            "joined": joined,
            "left": left,
            "now": members_now,
            "eligible_save_days": int(sav.obligations_due(ctx)[0]),
        },
        "balance_counts": {
            "started_with_balance": end_with_balance - new_balances + cleared_balance,
            "cleared_balance": cleared_balance,
            "new_balances": new_balances,
            "end_with_balance": end_with_balance,
        },
        "activity": {
            "busiest_days": busiest,
            "busiest_count": busiest_count,
            "quietest_days": quietest,
            "quietest_count": quietest_count,
        },
        "payout_rotation": {
            "this_week_completed_count": len(completed),
            "this_week_completed_names": _names_for(session, [p.user_id for p in completed]),
            "next_week_names": _names_for(session, [p.user_id for p in next_up]),
            "remain_after_next_payout": remaining,
        },
    }
