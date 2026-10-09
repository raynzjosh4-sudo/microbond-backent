from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional, Dict, Any

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.settings import (
    GroupFinancialSettings,
    GroupVisibilitySettings
)

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])

@router.get("/{group_id}/settings/financial", summary="Get Financial Rules (Privacy-Gated)")
def get_financial_settings(
    group_id: str, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the Financial Rules for the group. 
    If the requester is a regular member, the response is dynamically stripped
    based on the Admin's visibility toggles.
    """
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    
    if not membership:
        raise HTTPException(status_code=403, detail="You must be a member to view settings.")
        
    is_admin = membership.role == "ADMIN"
    
    fin_settings = session.exec(
        select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group_id)
    ).first()
    
    vis_settings = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()
    
    if not fin_settings or not vis_settings:
        raise HTTPException(status_code=404, detail="Settings not found.")
        
    # Convert settings to dictionary to easily pop hidden keys
    response_data = fin_settings.dict(exclude={"id", "group_id", "updated_at"})
    
    # If the user is NOT an Admin, apply the privacy strips!
    if not is_admin:
        if not vis_settings.vis_manage_payout_order:
            response_data.pop("payout_selection_strategy", None)
            
        if not vis_settings.vis_late_fee_penalties:
            response_data.pop("enable_late_fees", None)
            response_data.pop("late_fee_amount", None)
            response_data.pop("late_fee_frequency", None)
            
        if not vis_settings.vis_grace_period_window:
            response_data.pop("enable_grace_period", None)
            response_data.pop("grace_period_hours", None)
            
        if not vis_settings.vis_enforce_payout_holds:
            response_data.pop("enforce_payout_holds", None)
            
        if not vis_settings.vis_substitute_member_allowance:
            response_data.pop("allow_substitute_members", None)
            
        if not vis_settings.vis_pending_payout_queue:
            response_data.pop("max_pending_payouts", None)
            
        if not vis_settings.vis_time_lock_disbursals:
            response_data.pop("enable_timelock", None)
            response_data.pop("timelock_duration_hours", None)
            
        # Liquidity toggles
        if not vis_settings.vis_late_fee_escalation:
            # We don't have an escalation field yet, but if we did, we'd strip it here.
            pass
            
    return {"status": "success", "data": response_data}
