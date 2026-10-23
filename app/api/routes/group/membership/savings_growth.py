"""
Member Savings Growth Chart API.

GET /api/v1/groups/{group_id}/membership/me/savings-growth
  -> Returns time-bucketed cumulative savings for the current member.
     Powers the "View growth chart" screen on the Total Saved detail page.
"""
from typing import List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.finance import MemberObligation
from app.models.group.settings import GroupVisibilitySettings

router = APIRouter(prefix="/api/v1/groups", tags=["Member Savings Growth"])


@router.get(
    "/{group_id}/membership/me/savings-growth",
    summary="View savings growth chart for the current member"
)
def get_my_savings_growth(
    group_id: str,
    period: Literal["weekly", "monthly", "all_time"] = Query(
        default="monthly",
        description="Bucketing period: 'weekly', 'monthly', or 'all_time' (single cumulative total)"
    ),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Returns this member's cumulative savings over time, bucketed by week or month.
    Powers the "View growth chart — See how your savings have compounded over time" screen.
    Respects vis_member_total_savings: if admin hides savings, this returns 403.
    """
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You are not a member of this group.")

    # Respect the admin's vis_member_total_savings toggle
    vis = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()
    is_admin = (membership.role == "ADMIN")
    savings_allowed = is_admin or (getattr(vis, "vis_member_total_savings", True) if vis else True)
    if not savings_allowed:
        raise HTTPException(
            status_code=403,
            detail="The Group Admin has restricted members from viewing their savings data."
        )

    # Fetch all paid obligations for this member
    obligations = session.exec(
        select(MemberObligation).where(
            MemberObligation.group_id == group_id,
            MemberObligation.user_id == current_user.id,
            MemberObligation.amount_paid > 0
        ).order_by(MemberObligation.due_date)
    ).all()

    if not obligations:
        return {
            "status": "success",
            "meta": {
                "group_id": group_id,
                "currency": group.currency,
                "total_saved": 0,
                "interest_gained": 0,
                "period": period,
            },
            "points": []
        }

    # Bucket obligations by period
    from collections import defaultdict
    import datetime

    def _bucket_key(due_date_ms: int, period: str) -> str:
        dt = datetime.datetime.utcfromtimestamp(due_date_ms / 1000)
        if period == "weekly":
            # ISO week: e.g. "2026-W42"
            iso = dt.isocalendar()
            return f"{iso[0]}-W{iso[1]:02d}"
        elif period == "monthly":
            return dt.strftime("%Y-%m")
        else:
            return "all_time"

    bucket_totals: dict = defaultdict(float)
    bucket_order: list = []
    seen_keys: set = set()

    for ob in obligations:
        key = _bucket_key(ob.due_date, period)
        if key not in seen_keys:
            bucket_order.append(key)
            seen_keys.add(key)
        bucket_totals[key] += ob.amount_paid

    # Build cumulative series
    cumulative = 0.0
    points = []
    for key in bucket_order:
        cumulative += bucket_totals[key]
        points.append({
            "label": key,
            "amount_saved_in_period": bucket_totals[key],
            "cumulative_saved": round(cumulative, 2),
        })

    total_saved = membership.total_contributed or 0

    return {
        "status": "success",
        "meta": {
            "group_id": group_id,
            "group_name": group.name,
            "currency": group.currency,
            "total_saved": total_saved,
            "total_saved_formatted": f"{group.currency} {total_saved:,}",
            "interest_gained": 0,  # Future: wire to interest engine
            "period": period,
            "bucket_count": len(points),
        },
        "points": points
    }
