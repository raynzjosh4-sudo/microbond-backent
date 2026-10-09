from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.finance import MemberObligation

router = APIRouter(prefix="/api/v1/groups", tags=["Group Health"])

@router.get("/{group_id}/health", summary="Get Group Health & Rating Stats")
def get_group_health_rating(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # Verify group exists and user is a member
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    
    if not membership:
        raise HTTPException(status_code=403, detail="Access denied. Not a member of this group.")

    # 1. Calculate Trust Score Average
    members = session.exec(
        select(GroupMembership).where(GroupMembership.group_id == group_id)
    ).all()
    
    total_trust_score = sum(m.group_trust_score for m in members if m.group_trust_score is not None)
    scored_members = sum(1 for m in members if m.group_trust_score is not None)
    
    # If no one has a trust score yet, assume starting perfect score of 100
    average_trust_score = (total_trust_score / scored_members) if scored_members > 0 else 100.0
    
    # 2. Calculate On-Time Repayments & Default Rate
    obligations = session.exec(
        select(MemberObligation).where(MemberObligation.group_id == group_id)
    ).all()
    
    total_obligations = len(obligations)
    if total_obligations == 0:
        return {
            "health_grade": "A+",
            "status": "Excellent Standing",
            "metrics": {
                "on_time_repayment_rate": "100%",
                "active_default_rate": "0%",
                "average_trust_score": f"{int(average_trust_score)}/100"
            }
        }
        
    on_time_count = sum(1 for o in obligations if o.status == "PAID") # Note: assuming late payments have different logic, but simple count for now
    default_count = sum(1 for o in obligations if o.status == "DEFAULTED")
    late_count = sum(1 for o in obligations if o.status == "LATE")
    
    # Technically, anything paid is "repaid". "On-time" implies PAID without ever hitting LATE. 
    # For now, we calculate percentage of PAID obligations against (PAID + LATE + DEFAULTED)
    completed_obligations = on_time_count + late_count + default_count
    
    if completed_obligations > 0:
        on_time_percentage = (on_time_count / completed_obligations) * 100
        default_percentage = (default_count / completed_obligations) * 100
    else:
        on_time_percentage = 100.0
        default_percentage = 0.0

    # 3. Determine Grade based on stats
    grade = "A+"
    status = "Excellent Standing"
    
    if default_percentage > 10:
        grade = "D"
        status = "High Risk"
    elif default_percentage > 0 or on_time_percentage < 80:
        grade = "C"
        status = "Needs Improvement"
    elif on_time_percentage < 95:
        grade = "B"
        status = "Good Standing"
        
    return {
        "health_grade": grade,
        "status": status,
        "metrics": {
            "on_time_repayment_rate": f"{int(on_time_percentage)}%",
            "active_default_rate": f"{int(default_percentage)}%",
            "average_trust_score": f"{int(average_trust_score)}/100"
        }
    }
