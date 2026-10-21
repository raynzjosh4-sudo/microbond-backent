"""
Metric registry: single source of truth for every metric the Chart Builder can plot.

The Android app builds its X/Y axis lists from /analytics/catalog (generated from this
registry), so adding a metric here is all that is needed for it to appear in the app.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from app.services.analytics.metrics import members as mem
from app.services.analytics.metrics import payouts as pay
from app.services.analytics.metrics import saving as sav

SAVING, MEMBERS, PAYOUTS = "SAVING", "MEMBERS", "PAYOUTS"
SERIES, CATEGORICAL, SNAPSHOT = "series", "categorical", "snapshot"

NUMERIC_CHARTS = ["bar", "line", "area", "scatter", "waterfall"]


@dataclass(frozen=True)
class MetricDef:
    id: str
    label: str
    category: str
    unit: str
    icon: str
    compute: Optional[Callable] = None        # ctx -> one value per bucket
    snapshot: Optional[Callable] = None       # ctx -> {"value", "label"} | None  (SNAPSHOT kind)
    kind: str = SERIES
    allowed_charts: tuple = tuple(NUMERIC_CHARTS)
    recommended_chart: str = "bar"
    gate: Optional[Callable[[Any], bool]] = None  # visibility settings -> may a non-admin see it?
    value_labels: Optional[tuple] = None      # for categorical metrics, e.g. weekday names
    hidden: bool = False                      # usable by the API but not listed in the catalog
    description: str = ""


# ── Visibility gates (mirrors the privacy rules already used by the weekly report) ──
def _money_visible(vis) -> bool:
    return bool(vis and vis.vis_report_actual_collection)


def _balance_visible(vis) -> bool:
    return bool(vis and vis.vis_report_actual_collection and not vis.hide_total_group_balance)


def _payouts_visible(vis) -> bool:
    return bool(vis and vis.vis_manage_payout_order)


_METRICS: List[MetricDef] = [
    # ── Saving ──
    MetricDef("daily_saving", "Daily saving", SAVING, "UGX", "payments",
              sav.daily_saving, gate=_money_visible,
              description="Money deposited (settled ledger deposits) in each period."),
    MetricDef("successful_save_days", "Successful save-days", SAVING, "days", "calendar",
              sav.successful_save_days, description="Obligations with any amount paid."),
    MetricDef("full_save_days", "Full-save days", SAVING, "days", "calendar",
              sav.full_save_days, description="Obligations paid in full."),
    MetricDef("partial_save_days", "Partial-save days", SAVING, "days", "bar_chart",
              sav.partial_save_days, description="Obligations paid in part."),
    MetricDef("no_save_days", "No-save days", SAVING, "days", "warning",
              sav.no_save_days, description="Obligations already due with nothing paid."),
    MetricDef("average_saving_streak", "Average saving streak", SAVING, "days", "star",
              sav.average_saving_streak, recommended_chart="line",
              description="Average run of consecutive successful save-days per member."),
    MetricDef("missed_saving_rate", "Missed-saving rate", SAVING, "%", "percent",
              sav.missed_saving_rate, recommended_chart="line",
              description="Share of resolved save-days with nothing paid."),
    MetricDef("total_accumulation", "Total accumulation", SAVING, "UGX", "account_balance",
              sav.total_accumulation, gate=_balance_visible, recommended_chart="area",
              description="Total saved to date (cumulative deposits)."),
    MetricDef("week_over_week_change", "Week-over-week change", SAVING, "%", "swap",
              sav.period_change, gate=_money_visible, recommended_chart="line",
              description="% change in deposits vs the previous period."),
    MetricDef("busiest_saving_day", "Busiest saving day", SAVING, "weekday", "trending_up",
              sav.busiest_saving_day, kind=CATEGORICAL, allowed_charts=("scatter",),
              recommended_chart="scatter", value_labels=tuple(sav.WEEKDAYS),
              description="Weekday with the most deposits in each period."),
    MetricDef("target_met_rate", "Target met rate", SAVING, "%", "target",
              sav.target_met_rate, recommended_chart="line",
              description="Share of resolved save-days paid in full."),
    MetricDef("total_group_activity", "Total group activity", SAVING, "events", "activity",
              sav.total_group_activity, recommended_chart="line",
              description="Deposits, payouts, joins, leaves and chat messages."),
    MetricDef("average_deposit_size", "Average deposit size", SAVING, "UGX", "payments",
              sav.average_deposit_size, gate=_money_visible, recommended_chart="line",
              description="Average size of a settled deposit."),
    # ── Members ──
    MetricDef("active_members", "Active members", MEMBERS, "members", "group",
              mem.active_members, recommended_chart="line",
              description="Members on the roster at the end of each period."),
    MetricDef("new_members", "New members", MEMBERS, "members", "person_add",
              mem.new_members, description="Members who joined in each period."),
    MetricDef("members_with_balance", "Members with balance", MEMBERS, "members", "warning",
              mem.members_with_balance, recommended_chart="line",
              description="Members who owe the group money at the end of each period."),
    MetricDef("members_cleared_balance", "Members who cleared balance", MEMBERS, "members", "check_circle",
              mem.members_cleared_balance, description="Members who went from owing to paid up."),
    MetricDef("members_left", "Members who left", MEMBERS, "members", "person_remove",
              mem.members_left, hidden=True),
    MetricDef("members_new_balance", "Members who started owing", MEMBERS, "members", "warning",
              mem.members_new_balance, hidden=True),
    MetricDef("obligations_due", "Obligations due", SAVING, "days", "calendar",
              sav.obligations_due, hidden=True),
    # ── Payouts ──
    MetricDef("members_paid_out", "Members paid out", PAYOUTS, "members", "paid",
              mem.members_paid_out, gate=_payouts_visible,
              description="Distinct members who received a completed payout."),
    MetricDef("payouts_completed", "Payouts completed", PAYOUTS, "payouts", "trending_up",
              pay.payouts_completed, gate=_payouts_visible),
    MetricDef("payouts_pending", "Payouts pending", PAYOUTS, "payouts", "alarm",
              pay.payouts_pending, gate=_payouts_visible,
              description="Payouts scheduled in the period that have not completed."),
    MetricDef("next_payout_date", "Next payout date", PAYOUTS, "date", "calendar",
              snapshot=pay.next_payout_date, kind=SNAPSHOT, allowed_charts=(),
              gate=_payouts_visible, description="Earliest upcoming unpaid payout."),
    MetricDef("payout_progress", "Payout progress", PAYOUTS, "%", "speed",
              pay.payout_progress, gate=_payouts_visible, recommended_chart="line",
              description="% of scheduled payouts completed by the end of each period."),
]

REGISTRY: Dict[str, MetricDef] = {m.id: m for m in _METRICS}
CATALOG_ORDER: List[MetricDef] = [m for m in _METRICS if not m.hidden]


def is_available(metric: MetricDef, vis_settings: Any, is_admin: bool) -> bool:
    return is_admin or metric.gate is None or metric.gate(vis_settings)
