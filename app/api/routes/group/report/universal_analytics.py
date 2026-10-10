from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy import func

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership, Group
from app.models.group.finance import MemberObligation, GroupPenalty, GroupPayout, GuarantorPledge, TurnSwapRequest
from app.models.group.chat import GroupChatMessage
from app.models.group.report import GroupReport

router = APIRouter(prefix="/api/v1/groups", tags=["Universal Analytics"])

def get_start_time_ms(days: int) -> int:
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return int(dt.timestamp() * 1000)

@router.get("/{group_id}/analytics/metric", summary="Universal Dynamic Graphing Engine")
def get_dynamic_metric(
    group_id: str,
    metric: str = Query(..., description="The ID of the metric to plot (e.g., 'penalties_collected', 'total_contributions')"),
    timeframe_days: int = Query(30, description="Number of days to look back"),
    aggregate_by: str = Query("day", description="Granularity: 'day', 'week', or 'month'"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    A single, highly scalable engine that processes any of the 200+ data points 
    and returns a standardized envelope for frontend charting libraries.
    """
    # 1. Security Check
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    
    if not membership:
        raise HTTPException(status_code=403, detail="Access denied.")

    start_ms = get_start_time_ms(timeframe_days)
    
    # 2. Metric Configuration Dictionary
    # This acts as the factory routing for all 200+ potential metrics
    METRICS_REGISTRY = {
        "penalties_collected": {
            "title": "Total Penalties Collected",
            "y_axis_label": "Amount",
            "unit": "UGX",
            "model": GroupPenalty,
            "time_field": GroupPenalty.created_at,
            "value_field": GroupPenalty.penalty_amount,
            "aggregation": "sum",
            "filters": [GroupPenalty.is_paid == True],
            "chart_type": "line_chart"
        },
        "penalties_issued": {
            "title": "Total Penalties Issued (Unpaid & Paid)",
            "y_axis_label": "Amount",
            "unit": "UGX",
            "model": GroupPenalty,
            "time_field": GroupPenalty.created_at,
            "value_field": GroupPenalty.penalty_amount,
            "aggregation": "sum",
            "filters": [],
            "chart_type": "bar_chart"
        },
        "penalty_amount": {
            "title": "Total Penalty Amount",
            "y_axis_label": "Amount",
            "unit": "UGX",
            "model": GroupPenalty,
            "time_field": GroupPenalty.created_at,
            "value_field": GroupPenalty.penalty_amount,
            "aggregation": "sum",
            "filters": [],
            "chart_type": "bar_chart"
        },
        "total_contributions": {
            "title": "Actual Contributions Collected",
            "y_axis_label": "Amount",
            "unit": "UGX",
            "model": MemberObligation,
            "time_field": MemberObligation.updated_at,
            "value_field": MemberObligation.amount_paid,
            "aggregation": "sum",
            "filters": [MemberObligation.status == "PAID"],
            "chart_type": "area_chart"
        },
        "expected_collections": {
            "title": "Expected Revenue / Obligations",
            "y_axis_label": "Amount",
            "unit": "UGX",
            "model": MemberObligation,
            "time_field": MemberObligation.due_date,
            "value_field": MemberObligation.amount_due,
            "aggregation": "sum",
            "filters": [],
            "chart_type": "line_chart"
        },
        "missed_payments": {
            "title": "Defaulted & Late Funds",
            "y_axis_label": "Amount",
            "unit": "UGX",
            "model": MemberObligation,
            "time_field": MemberObligation.due_date,
            "value_field": MemberObligation.amount_due,
            "aggregation": "sum",
            "filters": [MemberObligation.status.in_(["LATE", "DEFAULTED"])],
            "chart_type": "bar_chart"
        },
        "payouts_released": {
            "title": "Capital Released to Members",
            "y_axis_label": "Amount",
            "unit": "UGX",
            "model": GroupPayout,
            "time_field": GroupPayout.payout_date,
            "value_field": GroupPayout.amount_received,
            "aggregation": "sum",
            "filters": [GroupPayout.status == "COMPLETED"],
            "chart_type": "step_line_chart"
        },
        "guarantor_exposure": {
            "title": "Guarantor Systemic Risk Exposure",
            "y_axis_label": "Liability Amount",
            "unit": "UGX",
            "model": GuarantorPledge, # Note: Requires import
            "time_field": GuarantorPledge.created_at,
            "value_field": GuarantorPledge.maximum_liability_amount,
            "aggregation": "sum",
            "filters": [GuarantorPledge.status == "ACTIVE"],
            "chart_type": "stacked_bar"
        },
        "member_growth": {
            "title": "New Member Joins",
            "y_axis_label": "Members",
            "unit": "People",
            "model": GroupMembership,
            "time_field": GroupMembership.joined_at,
            "value_field": GroupMembership.id, # We will count IDs
            "aggregation": "count",
            "filters": [GroupMembership.status == "ACTIVE"],
            "chart_type": "smooth_line_chart"
        },
        "turn_swaps_requested": {
            "title": "Turn Swap Market Volume",
            "y_axis_label": "Swap Requests",
            "unit": "Requests",
            "model": TurnSwapRequest, # Note: Requires import
            "time_field": TurnSwapRequest.created_at,
            "value_field": TurnSwapRequest.id,
            "aggregation": "count",
            "filters": [],
            "chart_type": "bar_chart"
        },
        "turn_swaps_completed": {
            "title": "Successful Turn Swaps",
            "y_axis_label": "Swaps",
            "unit": "Swaps",
            "model": TurnSwapRequest,
            "time_field": TurnSwapRequest.updated_at,
            "value_field": TurnSwapRequest.id,
            "aggregation": "count",
            "filters": [TurnSwapRequest.status == "ACCEPTED"],
            "chart_type": "bar_chart"
        },
        "average_deposit_size": {
            "title": "Average Deposit Size",
            "y_axis_label": "Amount",
            "unit": "UGX",
            "model": MemberObligation,
            "time_field": MemberObligation.updated_at,
            "value_field": MemberObligation.amount_paid,
            "aggregation": "avg",
            "filters": [MemberObligation.status == "PAID"],
            "chart_type": "line_chart"
        },
        "penalty_debt_outstanding": {
            "title": "Uncollected Bad Debt (Penalties)",
            "y_axis_label": "Amount",
            "unit": "UGX",
            "model": GroupPenalty,
            "time_field": GroupPenalty.created_at,
            "value_field": GroupPenalty.penalty_amount,
            "aggregation": "sum",
            "filters": [GroupPenalty.is_paid == False],
            "chart_type": "area_chart"
        },
        "late_payment_volume": {
            "title": "Late Payment Incidents",
            "y_axis_label": "Incidents",
            "unit": "Count",
            "model": MemberObligation,
            "time_field": MemberObligation.updated_at,
            "value_field": MemberObligation.id,
            "aggregation": "count",
            "filters": [MemberObligation.status == "LATE"],
            "chart_type": "bar_chart"
        },
        "guarantor_triggers": {
            "title": "Guarantor Collateral Seizures",
            "y_axis_label": "Incidents",
            "unit": "Count",
            "model": GuarantorPledge,
            "time_field": GuarantorPledge.created_at,
            "value_field": GuarantorPledge.id,
            "aggregation": "count",
            "filters": [GuarantorPledge.status == "TRIGGERED"],
            "chart_type": "bar_chart"
        },
        "payouts_on_hold": {
            "title": "Capital Locked in Escrow/Holds",
            "y_axis_label": "Amount",
            "unit": "UGX",
            "model": GroupPayout,
            "time_field": GroupPayout.payout_date,
            "value_field": GroupPayout.amount_expected,
            "aggregation": "sum",
            "filters": [GroupPayout.status == "ON_HOLD"],
            "chart_type": "step_line_chart"
        },
        "failed_payouts": {
            "title": "Failed Bank/Mobile Money Transfers",
            "y_axis_label": "Incidents",
            "unit": "Count",
            "model": GroupPayout,
            "time_field": GroupPayout.payout_date,
            "value_field": GroupPayout.id,
            "aggregation": "count",
            "filters": [GroupPayout.status == "FAILED"],
            "chart_type": "bar_chart"
        },
        "chat_activity": {
            "title": "Group Chat Engagement Volume",
            "y_axis_label": "Messages",
            "unit": "Messages",
            "model": GroupChatMessage,
            "time_field": GroupChatMessage.created_at,
            "value_field": GroupChatMessage.id,
            "aggregation": "count",
            "filters": [GroupChatMessage.message_type == "TEXT"],
            "chart_type": "line_chart"
        },
        "system_events": {
            "title": "Automated System Announcements",
            "y_axis_label": "Events",
            "unit": "Events",
            "model": GroupChatMessage,
            "time_field": GroupChatMessage.created_at,
            "value_field": GroupChatMessage.id,
            "aggregation": "count",
            "filters": [GroupChatMessage.message_type == "SYSTEM_EVENT"],
            "chart_type": "bar_chart"
        },
        "reports_filed": {
            "title": "Security & Abuse Reports",
            "y_axis_label": "Reports",
            "unit": "Incidents",
            "model": GroupReport,
            "time_field": GroupReport.created_at,
            "value_field": GroupReport.id,
            "aggregation": "count",
            "filters": [],
            "chart_type": "area_chart"
        },
        "member_churn": {
            "title": "Members Leaving Group",
            "y_axis_label": "Members",
            "unit": "People",
            "model": GroupMembership,
            "time_field": GroupMembership.left_at,
            "value_field": GroupMembership.id,
            "aggregation": "count",
            "filters": [GroupMembership.status == "LEFT", GroupMembership.left_at != None],
            "chart_type": "bar_chart"
        }
    }

    if metric not in METRICS_REGISTRY:
        raise HTTPException(status_code=400, detail=f"Metric '{metric}' is not registered in the Analytics Engine.")

    config = METRICS_REGISTRY[metric]
    
    # 3. Dynamic Database Query Engine
    model = config["model"]
    time_col = config["time_field"]
    val_col = config["value_field"]
    
    base_query = select(time_col, val_col).where(
        model.group_id == group_id,
        time_col >= start_ms
    )
    
    for f in config["filters"]:
        base_query = base_query.where(f)
        
    results = session.exec(base_query).all()
    
    # 4. Aggregation Logic (Bucketing by Timeframe)
    # Using python dictionaries to group data quickly
    aggregated_data = {}
    count_data = {} # Used for average calculation if needed
    
    aggregation_type = config.get("aggregation", "sum")
    
    for timestamp_ms, value in results:
        # Handle nulls
        if value is None and aggregation_type != "count":
            continue
            
        dt = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
        
        # Determine the X-Axis label based on requested granularity
        if aggregate_by == "month":
            x_label = dt.strftime("%Y-%m")
        elif aggregate_by == "week":
            # format as Year-Week (e.g. 2026-W41)
            x_label = dt.strftime("%Y-W%V")
        else: # default day
            x_label = dt.strftime("%Y-%m-%d")
            
        if x_label not in aggregated_data:
            aggregated_data[x_label] = 0.0
            count_data[x_label] = 0
            
        if aggregation_type == "sum":
            aggregated_data[x_label] += float(value)
        elif aggregation_type == "count":
            aggregated_data[x_label] += 1.0
        elif aggregation_type == "avg":
            aggregated_data[x_label] += float(value)
            count_data[x_label] += 1
            
    # Resolve averages
    if aggregation_type == "avg":
        for k in aggregated_data:
            if count_data[k] > 0:
                aggregated_data[k] = aggregated_data[k] / count_data[k]
        
    # Sort chronologically
    sorted_labels = sorted(aggregated_data.keys())
    
    data_points = [
        {"x": label, "y": aggregated_data[label]}
        for label in sorted_labels
    ]
    
    # 5. Compile the Standardized Frontend Envelope
    return {
        "status": "success",
        "chart_metadata": {
            "metric_id": metric,
            "display_title": config["title"],
            "y_axis_label": config["y_axis_label"],
            "y_axis_unit": config["unit"],
            "x_axis_label": "Time" if aggregate_by != "day" else "Date",
            "granularity": aggregate_by,
            "chart_type_recommendation": config["chart_type"]
        },
        "data_points": data_points
    }
