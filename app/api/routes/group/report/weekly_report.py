from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import Optional, List, Dict, Any, Literal
from datetime import date, datetime, timezone, timedelta
from pydantic import BaseModel, Field

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.finance import MemberObligation, GroupPayout
from app.models.group.settings import GroupVisibilitySettings, GroupFinancialSettings
from app.models.group.report import (
    GroupFinancialReport,
)
from app.services.analytics.buckets import BucketError
from app.services.analytics.period_summary import build_period_summary
from app.services.group.report_visibility import (
    REPORT_SECTION_BY_KEY,
    REPORT_SECTION_KEYS,
    available_report_sections,
    load_report_section_visibility,
    report_detail_visibility,
)

router = APIRouter(prefix="/api/v1/groups", tags=["Group Reports"])

def get_start_of_week(dt: datetime) -> datetime:
    # Assuming week starts on Monday
    return dt - timedelta(days=dt.weekday())


class ReportPeriod(BaseModel):
    type: Literal["WEEK", "MONTH", "CUSTOM"]
    selected_date: date
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class GenerateReportRequest(BaseModel):
    included_sections: List[str] = Field(min_length=1)
    period: ReportPeriod


def _get_active_membership(session: Session, group_id: str, user_id) -> GroupMembership:
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user_id,
            GroupMembership.status == "ACTIVE",
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You must be an active member of this group.")
    return membership


def _get_visibility_settings(session: Session, group_id: str) -> GroupVisibilitySettings:
    settings = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()
    return settings or GroupVisibilitySettings(group_id=group_id)


def _resolve_period(period: ReportPeriod) -> tuple[date, date]:
    if period.type == "WEEK":
        start = period.selected_date - timedelta(days=period.selected_date.weekday())
        return start, start + timedelta(days=6)
    if period.type == "MONTH":
        start = period.selected_date.replace(day=1)
        if start.month == 12:
            next_month = start.replace(year=start.year + 1, month=1)
        else:
            next_month = start.replace(month=start.month + 1)
        return start, next_month - timedelta(days=1)
    if period.start_date is None or period.end_date is None:
        raise HTTPException(
            status_code=400,
            detail="CUSTOM periods require start_date and end_date.",
        )
    if period.end_date < period.start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date.")
    return period.start_date, period.end_date


@router.get("/{group_id}/reports/available-sections", summary="List Report Sections Available to Me")
def get_available_report_sections(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    membership = _get_active_membership(session, group_id, current_user.id)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")
    visibility = load_report_section_visibility(session, group_id)
    return {
        "status": "success",
        "data": {
            "group_id": group_id,
            "group_type": group.type,
            "viewer_role": membership.role,
            "sections": available_report_sections(group.type, membership.role, visibility),
            "detail_visibility": report_detail_visibility(
                _get_visibility_settings(session, group_id)
            ),
        },
    }


@router.post("/{group_id}/reports", summary="Generate a Permission-Checked Group Report")
def generate_group_report(
    group_id: str,
    request: GenerateReportRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    membership = _get_active_membership(session, group_id, current_user.id)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")
    visibility = load_report_section_visibility(session, group_id)
    requested_keys = list(dict.fromkeys(request.included_sections))
    unknown_keys = [key for key in requested_keys if key not in REPORT_SECTION_BY_KEY]
    if unknown_keys:
        raise HTTPException(
            status_code=400,
            detail={"message": "Unknown report section keys.", "keys": unknown_keys},
        )

    allowed_keys = {
        section["key"]
        for section in available_report_sections(group.type, membership.role, visibility)
    }
    forbidden_keys = [key for key in requested_keys if key not in allowed_keys]
    if forbidden_keys:
        raise HTTPException(
            status_code=403,
            detail={"message": "One or more report sections are not visible to you.", "keys": forbidden_keys},
        )
    start_date, end_date = _resolve_period(request.period)
    days = (end_date - start_date).days + 1
    target_date_ms = int(
        datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000
    )
    report_data = get_custom_saving_report(
        group_id=group_id,
        days=days,
        target_date_ms=target_date_ms,
        session=session,
        current_user=current_user,
    )

    section_payload = {}
    for key in requested_keys:
        definition = REPORT_SECTION_BY_KEY[key]
        section_payload[key] = {
            field: report_data[field]
            for field in definition["fields"]
            if field in report_data
        }

    report = GroupFinancialReport(
        group_id=group_id,
        requester_user_id=current_user.id,
        period_type=request.period.type,
        selected_date=request.period.selected_date,
        start_date=start_date,
        end_date=end_date,
        included_sections=requested_keys,
        payload=section_payload,
    )
    session.add(report)
    session.commit()
    session.refresh(report)

    return {
        "status": "success",
        "data": {
            "report_id": report.report_id,
            "group_id": group_id,
            "viewer_role": membership.role,
            "included_sections": requested_keys,
            "period": {
                "type": request.period.type,
                "selected_date": request.period.selected_date.isoformat(),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "sections": [
                {
                    "key": key,
                    "label": REPORT_SECTION_BY_KEY[key]["label"],
                    "data": section_payload[key],
                }
                for key in requested_keys
            ],
        },
    }

@router.get("/{group_id}/reports/custom", summary="Get Custom Savings Report Data")
def get_custom_saving_report(
    group_id: str,
    days: int = Query(default=7, description="Number of days to look back"),
    target_date_ms: Optional[int] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Generates the comprehensive Weekly Savings Report data for the frontend to display.
    """
    # 1. Verify access
    membership = _get_active_membership(session, group_id, current_user.id)

    # 2. Determine time window
    if target_date_ms:
        current_dt = datetime.fromtimestamp(target_date_ms / 1000.0, tz=timezone.utc)
    else:
        current_dt = datetime.now(timezone.utc)
        
    end_of_period = current_dt.replace(hour=23, minute=59, second=59, microsecond=0)
    start_of_period = (end_of_period - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    start_ms = int(start_of_period.timestamp() * 1000)
    end_ms = int(end_of_period.timestamp() * 1000)

    # 3. Members stats
    all_members = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.status == "ACTIVE",
        )
    ).all()
    total_members = len(all_members)
    
    # 4. Obligations for this period
    period_obligations = session.exec(
        select(MemberObligation).where(
            MemberObligation.group_id == group_id,
            MemberObligation.due_date >= start_ms,
            MemberObligation.due_date <= end_ms
        )
    ).all()
    
    # Fetch settings for visibility and reserve fund math
    vis_settings = _get_visibility_settings(session, group_id)
    fin_settings = session.exec(select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group_id)).first()
    is_admin = membership.role == "ADMIN"
    
    expected_revenue = 0.0
    actual_collection = 0.0

    # Aggregate Daily Savings
    # We will format this exactly for the UI: Mon, Tue, Wed...
    days_map = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    daily_saving = {day: {"full": 0, "partial": 0, "no_save": 0, "eligible": total_members} for day in days_map}
    
    week_totals = {
        "full_days": 0,
        "partial_days": 0,
        "no_save_days": 0,
        "members_saved_at_least_once": 0,
        "successful_save_days": 0,
        "full_every_eligible_day": 0,
        "partial_no_missed_days": 0,
        "missed_1_plus_days": 0,
        "no_saving_all_week": 0
    }
    
    member_savings_count = {m.user_id: 0 for m in all_members}
    
    # Detailed member stats with IDs
    member_stats = {
        str(m.user_id): {
            "full_deposits": 0,
            "half_deposits": 0,
            "not_deposited": 0
        } for m in all_members
    }
    
    # Simple deposit status overview
    deposit_status = {
        "FULL_DEPOSIT": 0,
        "HALF_DEPOSIT": 0,
        "NOT_DEPOSITED": 0
    }

    for ob in period_obligations:
        ob_dt = datetime.fromtimestamp(ob.due_date / 1000.0, tz=timezone.utc)
        day_str = days_map[ob_dt.weekday()]
        user_id_str = str(ob.user_id)
        
        expected_revenue += ob.amount_due
        actual_collection += ob.amount_paid
        
        if ob.amount_paid >= ob.amount_due:
            daily_saving[day_str]["full"] += 1
            week_totals["full_days"] += 1
            week_totals["successful_save_days"] += 1
            member_savings_count[ob.user_id] += 1
            deposit_status["FULL_DEPOSIT"] += 1
            if user_id_str in member_stats:
                member_stats[user_id_str]["full_deposits"] += 1
                
        elif ob.amount_paid > 0:
            daily_saving[day_str]["partial"] += 1
            week_totals["partial_days"] += 1
            week_totals["successful_save_days"] += 1
            member_savings_count[ob.user_id] += 1
            deposit_status["HALF_DEPOSIT"] += 1
            if user_id_str in member_stats:
                member_stats[user_id_str]["half_deposits"] += 1
                
        else:
            daily_saving[day_str]["no_save"] += 1
            week_totals["no_save_days"] += 1
            deposit_status["NOT_DEPOSITED"] += 1
            if user_id_str in member_stats:
                member_stats[user_id_str]["not_deposited"] += 1

    # Calculate member aggregates
    for uid, count in member_savings_count.items():
        if count > 0:
            week_totals["members_saved_at_least_once"] += 1
            if count == 7: # Assuming daily savings
                week_totals["full_every_eligible_day"] += 1
            else:
                week_totals["missed_1_plus_days"] += 1
        else:
            week_totals["no_saving_all_week"] += 1

    # 5. Payout Rotation & Escrow Holds
    payouts_in_period = session.exec(
        select(GroupPayout).where(
            GroupPayout.group_id == group_id,
            GroupPayout.payout_date >= start_ms,
            GroupPayout.payout_date <= end_ms
        )
    ).all()
    
    payouts_completed = [p for p in payouts_in_period if p.status == "COMPLETED"]
    payouts_on_hold = [p for p in payouts_in_period if p.status == "ON_HOLD"]
    escrow_holds_amount = sum(p.amount_expected for p in payouts_on_hold)
    
    deficit = expected_revenue - actual_collection
    if deficit < 0: deficit = 0.0
    
    reserve_fund_pct = fin_settings.reserve_fund_percentage if fin_settings else 0.0
    reserve_fund_growth = actual_collection * (reserve_fund_pct / 100.0)
    
    # 6. Real values for what used to be hardcoded stubs (joined/left, balances, activity, payout names)
    try:
        summary = build_period_summary(
            session, group_id, start_ms, end_ms + 1000, int(datetime.now(timezone.utc).timestamp() * 1000)
        )
    except BucketError as e:
        raise HTTPException(status_code=400, detail=str(e))

    member_ids = [member.user_id for member in all_members]
    user_rows = session.exec(
        select(User.id, User.full_name).where(User.id.in_(member_ids))
    ).all() if member_ids else []
    names_by_id = {str(user_id): full_name or "Member" for user_id, full_name in user_rows}

    members_who_saved = []
    members_who_missed = []
    for user_id, stats in member_stats.items():
        entry = {
            "user_id": user_id,
            "name": names_by_id.get(user_id, "Member"),
            "full_deposits": stats["full_deposits"],
            "partial_deposits": stats["half_deposits"],
            "missed_deposits": stats["not_deposited"],
        }
        if stats["full_deposits"] + stats["half_deposits"] > 0:
            members_who_saved.append(entry)
        if stats["not_deposited"] > 0:
            members_who_missed.append(entry)

    contribution_history = [
        {
            "user_id": str(obligation.user_id),
            "member_name": names_by_id.get(str(obligation.user_id), "Member"),
            "due_date": obligation.due_date,
            "amount_due": obligation.amount_due,
            "amount_paid": obligation.amount_paid,
            "status": obligation.status,
        }
        for obligation in period_obligations
    ]
    all_member_names = [
        {
            "user_id": str(member.user_id),
            "name": names_by_id.get(str(member.user_id), "Member"),
            "role": member.role,
        }
        for member in all_members
    ]

    # 7. Build the report payload from persisted group and payment data.
    report_data = {
        "report_period": f"{start_of_period.strftime('%d %b')} - {end_of_period.strftime('%d %b %Y')}",
        "days_analyzed": days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "deposit_status": deposit_status,
        "member_stats": member_stats,
        "members": summary["members"],
        "daily_saving": daily_saving,
        "week_totals": week_totals,
        "balance_counts": summary["balance_counts"],
        "activity": summary["activity"],
        "payout_rotation": summary["payout_rotation"],
        "members_who_saved": members_who_saved,
        "members_who_missed": members_who_missed,
        "contribution_history": contribution_history,
        "all_members": all_member_names,
    }

    section_visibility = load_report_section_visibility(session, group_id)
    if not is_admin:
        for section in REPORT_SECTION_BY_KEY.values():
            if not section_visibility[section["key"]]:
                for field_name in section["fields"]:
                    report_data.pop(field_name, None)
        if not vis_settings.vis_member_total_savings:
            report_data.pop("balance_counts", None)
            report_data.pop("member_stats", None)
    
    # Add privacy-gated financial metrics
    if is_admin or (vis_settings and vis_settings.vis_report_expected_revenue):
        report_data["financials_expected_revenue"] = expected_revenue
    if is_admin or (vis_settings and vis_settings.vis_report_actual_collection):
        report_data["financials_actual_collection"] = actual_collection
    if is_admin or (vis_settings and vis_settings.vis_report_deficit):
        report_data["financials_deficit"] = deficit
    if is_admin or (vis_settings and vis_settings.vis_report_reserve_fund):
        report_data["financials_reserve_fund_growth"] = reserve_fund_growth
    if is_admin or (vis_settings and vis_settings.vis_report_escrow_holds):
        report_data["financials_escrow_holds_amount"] = escrow_holds_amount
        report_data["financials_escrow_holds_count"] = len(payouts_on_hold)
        
    return report_data
