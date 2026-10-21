from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.finance import MemberObligation, GroupPayout
from app.models.group.settings import GroupVisibilitySettings, GroupFinancialSettings
from app.services.analytics.buckets import BucketError
from app.services.analytics.period_summary import build_period_summary

router = APIRouter(prefix="/api/v1/groups", tags=["Group Reports"])

def get_start_of_week(dt: datetime) -> datetime:
    # Assuming week starts on Monday
    return dt - timedelta(days=dt.weekday())

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
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this group.")

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
    all_members = session.exec(select(GroupMembership).where(GroupMembership.group_id == group_id)).all()
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
    vis_settings = session.exec(select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)).first()
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

    # 7. Build the final report payload matching UI exactly
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
        "payout_rotation": summary["payout_rotation"]
    }
    
    # Apply Payout Rules Visibility
    if not is_admin and (not vis_settings or not vis_settings.vis_manage_payout_order):
        # Hide payout rotation details from members if the admin toggled it off
        report_data.pop("payout_rotation", None)
    
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
