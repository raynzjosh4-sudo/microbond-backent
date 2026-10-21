"""
Chart Builder API.

GET /api/v1/groups/{group_id}/analytics/catalog  -> every metric the caller may plot
GET /api/v1/groups/{group_id}/analytics/series   -> data points for the chosen X / Y metrics

The range is any number of days (or an explicit start/end) and the bucket size is any
number of days (or a calendar month/year), so the app is not limited to day/week/month.
"""
import time
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.models.group.group import GroupMembership
from app.models.group.settings import GroupVisibilitySettings
from app.models.user.user import User
from app.services.analytics.buckets import (
    MAX_BUCKETS,
    MAX_RANGE_DAYS,
    TIMEZONE_NAME,
    BucketError,
    build_plan,
)
from app.services.analytics.context import AnalyticsContext
from app.services.analytics.registry import (
    CATALOG_ORDER,
    REGISTRY,
    SNAPSHOT,
    MetricDef,
    is_available,
)

router = APIRouter(prefix="/api/v1/groups", tags=["Chart Builder Analytics"])


def _authorize(session: Session, group_id: str, user: User):
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user.id,
        )
    ).first()
    if not membership or (membership.status or "").upper() != "ACTIVE":
        raise HTTPException(status_code=403, detail="Access denied. You must be an active member of this group.")

    vis = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()
    return membership.role == "ADMIN", vis


def _round(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(float(value), 2)


@router.get("/{group_id}/analytics/catalog", summary="List every metric available to the Chart Builder")
def get_analytics_catalog(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    is_admin, vis = _authorize(session, group_id, current_user)
    now_ms = int(time.time() * 1000)
    ctx = AnalyticsContext(build_plan(now_ms, days=1), now_ms, session, group_id)

    metrics: List[Dict[str, Any]] = []
    for m in CATALOG_ORDER:
        available = is_available(m, vis, is_admin)
        entry: Dict[str, Any] = {
            "id": m.id,
            "label": m.label,
            "category": m.category,
            "icon": m.icon,
            "unit": m.unit,
            "kind": m.kind,
            "allowed_charts": list(m.allowed_charts),
            "recommended_chart": m.recommended_chart,
            "description": m.description,
            "available": available,
        }
        if m.value_labels:
            entry["value_labels"] = list(m.value_labels)
        if m.kind == SNAPSHOT:
            # Snapshots can't be plotted over time; ship their current value instead.
            entry["snapshot"] = m.snapshot(ctx) if available else None
        metrics.append(entry)

    return {
        "status": "success",
        "limits": {"max_range_days": MAX_RANGE_DAYS, "max_buckets": MAX_BUCKETS},
        "timezone": TIMEZONE_NAME,
        "metrics": metrics,
    }


def _resolve_metric(metric_id: str, param: str, vis, is_admin: bool) -> MetricDef:
    metric = REGISTRY.get(metric_id)
    if metric is None:
        raise HTTPException(status_code=400, detail=f"Unknown metric '{metric_id}' for '{param}'.")
    if not is_available(metric, vis, is_admin):
        raise HTTPException(status_code=403, detail=f"'{metric.label}' is hidden by the group admin.")
    if metric.kind == SNAPSHOT:
        raise HTTPException(
            status_code=422,
            detail=f"'{metric.label}' is a single value, not a series. Read it from /analytics/catalog.",
        )
    return metric


@router.get("/{group_id}/analytics/series", summary="Chart Builder data (any range, any bucket size)")
def get_analytics_series(
    group_id: str,
    y: str = Query(..., description="Y-axis metric id (see /analytics/catalog)"),
    x: str = Query("time", description="'time' or another metric id"),
    days: Optional[int] = Query(None, ge=1, le=MAX_RANGE_DAYS, description="Look back this many days (default 30)"),
    start_ms: Optional[int] = Query(None, description="Explicit range start (epoch ms); use with end_ms"),
    end_ms: Optional[int] = Query(None, description="Explicit range end (epoch ms); use with start_ms"),
    bucket_days: Optional[int] = Query(None, ge=1, description="Bucket width in days. Omit to auto-pick (~30 points)."),
    calendar_bucket: Optional[Literal["month", "year"]] = Query(None, description="Calendar-aligned buckets"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    is_admin, vis = _authorize(session, group_id, current_user)

    y_metric = _resolve_metric(y, "y", vis, is_admin)
    x_metric = None if x == "time" else _resolve_metric(x, "x", vis, is_admin)

    now_ms = int(time.time() * 1000)
    try:
        plan = build_plan(now_ms, days, start_ms, end_ms, bucket_days, calendar_bucket)
    except BucketError as e:
        raise HTTPException(status_code=400, detail=str(e))

    ctx = AnalyticsContext(plan, now_ms, session, group_id)
    y_values = y_metric.compute(ctx)
    x_values = x_metric.compute(ctx) if x_metric else None

    points = []
    for k, b in enumerate(plan.buckets):
        point: Dict[str, Any] = {
            "bucket_start": b.start_ms,
            "bucket_end": b.end_ms,
            "label": b.label,
            "x": b.x_label if x_metric is None else _round(x_values[k]),
            "y": _round(y_values[k]),
        }
        if y_metric.value_labels and y_values[k] is not None:
            point["y_text"] = y_metric.value_labels[int(y_values[k])]
        if x_metric and x_metric.value_labels and x_values[k] is not None:
            point["x_text"] = x_metric.value_labels[int(x_values[k])]
        points.append(point)

    return {
        "status": "success",
        "meta": {
            "x": x,
            "y": y,
            "x_label": "Time" if x_metric is None else x_metric.label,
            "y_label": y_metric.label,
            "y_unit": y_metric.unit,
            "x_unit": None if x_metric is None else x_metric.unit,
            "range": {"start_ms": plan.start_ms, "end_ms": plan.end_ms},
            "bucket_days": plan.bucket_days,
            "calendar_bucket": plan.calendar_bucket,
            "bucket_count": len(plan),
            "timezone": TIMEZONE_NAME,
            "recommended_chart": y_metric.recommended_chart,
            "allowed_charts": list(y_metric.allowed_charts),
        },
        "points": points,
    }
