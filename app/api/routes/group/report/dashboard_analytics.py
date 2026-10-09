from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta
import statistics

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.finance import MemberObligation

router = APIRouter(prefix="/api/v1/groups", tags=["Group Reports"])

def get_month_key(timestamp_ms: int) -> str:
    dt = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
    return dt.strftime("%Y-%m")

@router.get("/{group_id}/reports/dashboard", summary="Dashboard Analytics Data")
def get_dashboard_analytics(
    group_id: str,
    months_lookback: int = Query(6, description="Number of months to analyze"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns data for Box Plot (Deposit Distribution) and Heatmap (Member Payment Activity)
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

    # 2. Time boundaries
    now = datetime.now(timezone.utc)
    # Approximate months to days (30 days/month)
    start_dt = now - timedelta(days=months_lookback * 30)
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(now.timestamp() * 1000)
    
    # 3. Fetch all obligations in this period
    obligations = session.exec(
        select(MemberObligation).where(
            MemberObligation.group_id == group_id,
            MemberObligation.due_date >= start_ms,
            MemberObligation.due_date <= end_ms
        )
    ).all()
    
    # 4. Fetch all members for mapping names
    all_members = session.exec(
        select(GroupMembership).where(GroupMembership.group_id == group_id)
    ).all()
    
    # We will need user info
    users = session.exec(
        select(User).where(User.id.in_([m.user_id for m in all_members]))
    ).all()
    user_map = {str(u.id): u.full_name or "Unknown Member" for u in users}
    
    # Data structures for processing
    user_deposits: Dict[str, List[float]] = {str(m.user_id): [] for m in all_members}
    user_monthly_activity: Dict[str, Dict[str, str]] = {str(m.user_id): {} for m in all_members}
    
    # Extract unique months for the heatmap grid
    unique_months = set()
    
    for ob in obligations:
        uid = str(ob.user_id)
        if uid not in user_deposits:
            continue
            
        # Box plot data (amount paid)
        user_deposits[uid].append(ob.amount_paid)
        
        # Heatmap data
        month_key = get_month_key(ob.due_date)
        unique_months.add(month_key)
        
        # If any obligation in this month was missed/late, mark the whole month as Missed, else Paid
        # "Green = paid, Red = missed"
        is_paid = ob.amount_paid >= ob.amount_due
        
        if month_key not in user_monthly_activity[uid]:
            user_monthly_activity[uid][month_key] = "Paid" if is_paid else "Missed"
        else:
            # If they already had a Missed this month, it stays Missed
            if not is_paid:
                user_monthly_activity[uid][month_key] = "Missed"

    sorted_months = sorted(list(unique_months))
    
    # 5. Build Box Plot Data
    box_plot_data = []
    for uid, deposits in user_deposits.items():
        if not deposits:
            continue
            
        deposits.sort()
        try:
            # Requires Python 3.8+
            quantiles = statistics.quantiles(deposits, n=4)
            q1 = quantiles[0]
            median = quantiles[1]
            q3 = quantiles[2]
        except statistics.StatisticsError:
            # If not enough data points (e.g. 1 point), fallback
            val = deposits[0]
            q1 = median = q3 = val
            
        box_plot_data.append({
            "user_id": uid,
            "name": user_map.get(uid, "Unknown"),
            "min": min(deposits),
            "q1": q1,
            "median": median,
            "q3": q3,
            "max": max(deposits),
            "data_points": len(deposits)
        })

    # 6. Build Heatmap Data
    heatmap_data = []
    for uid, activity in user_monthly_activity.items():
        month_list = []
        for month in sorted_months:
            # If no obligation in this month, mark as "No Activity"
            status = activity.get(month, "No Activity")
            month_list.append({
                "month": month,
                "status": status
            })
            
        heatmap_data.append({
            "user_id": uid,
            "name": user_map.get(uid, "Unknown"),
            "months": month_list
        })
        
    return {
        "status": "success",
        "data": {
            "period": f"Last {months_lookback} months",
            "deposit_distribution_boxplot": box_plot_data,
            "member_payment_heatmap": {
                "columns": sorted_months,
                "rows": heatmap_data
            }
        }
    }
