from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.settings import (
    GroupGovernanceSettings,
    GroupVisibilitySettings,
    GroupFinancialSettings,
    GroupCommunicationSettings
)

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings Manifest"])

@router.get("/{group_id}/settings/manifest", summary="Get Dynamic Settings Access Manifest")
def get_settings_manifest(
    group_id: str, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns a unified manifest that tells the frontend exactly which settings 
    are visible, hidden, read-only, or editable for the current user based on 
    their role and the Admin's visibility toggles.
    """
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    
    if not membership:
        raise HTTPException(status_code=403, detail="Not a member of this group.")
        
    is_admin = membership.role == "ADMIN"
    
    gov_settings = session.exec(select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group_id)).first()
    vis_settings = session.exec(select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)).first()
    
    if not gov_settings or not vis_settings:
        raise HTTPException(status_code=404, detail="Settings not found.")
        
    members_can_edit = gov_settings.members_can_edit_settings
    
    # Define the 3 core Access Roles for the frontend
    # 1. ADMIN_ONLY: Pure structural rules. Members can only view them if visibility is ON.
    # 2. ADMIN_AND_USER: Personal preferences. Every user can view/edit their own.
    # 3. USER_AFTER_ADMIN_ALLOWED: Group settings that become editable by members if `members_can_edit_settings` is ON.
    
    manifest = {
        "group_id": group_id,
        "user_role": membership.role,
        "global_members_can_edit": members_can_edit,
        "categories": {
            "financial_rules": {},
            "governance_rules": {},
            "privacy_and_records": {},
            "personal_preferences": {}
        }
    }
    
    def add_setting(category, key, role_type, is_visible_to_member):
        # Calculate final frontend permissions
        can_view = is_admin or is_visible_to_member
        
        can_edit = False
        if is_admin:
            can_edit = True
        elif role_type == "ADMIN_AND_USER":
            can_edit = True
        elif role_type == "USER_AFTER_ADMIN_ALLOWED" and members_can_edit:
            can_edit = True
            
        manifest["categories"][category][key] = {
            "access_role": role_type,
            "can_view": can_view,
            "can_edit": can_edit,
            "is_hidden_by_admin": not is_visible_to_member if not is_admin else False
        }

    # --- FINANCIAL RULES (Admin Only) ---
    add_setting("financial_rules", "late_fee_amount", "ADMIN_ONLY", vis_settings.vis_late_fee_penalties)
    add_setting("financial_rules", "grace_period_hours", "ADMIN_ONLY", vis_settings.vis_grace_period_window)
    add_setting("financial_rules", "enforce_payout_holds", "ADMIN_ONLY", vis_settings.vis_enforce_payout_holds)
    add_setting("financial_rules", "reserve_fund_percentage", "ADMIN_ONLY", vis_settings.vis_liquidity_buffer_coverage)
    add_setting("financial_rules", "payout_selection_strategy", "ADMIN_ONLY", vis_settings.vis_manage_payout_order)
    
    # --- GOVERNANCE RULES (Admin Only) ---
    add_setting("governance_rules", "require_multi_signature", "ADMIN_ONLY", vis_settings.vis_require_multi_signature)
    add_setting("governance_rules", "quorum_percentage", "ADMIN_ONLY", vis_settings.vis_approval_quorum)
    add_setting("governance_rules", "require_guarantors", "ADMIN_ONLY", vis_settings.vis_guarantor_required)
    add_setting("governance_rules", "minimum_trust_score", "ADMIN_ONLY", vis_settings.vis_guarantor_required)
    
    # --- PRIVACY & RECORDS (User After Admin Allowed) ---
    add_setting("privacy_and_records", "group_charter_url", "USER_AFTER_ADMIN_ALLOWED", True) # Always visible
    add_setting("privacy_and_records", "chat_history_cleanup_days", "USER_AFTER_ADMIN_ALLOWED", vis_settings.vis_chat_history_cleanup)
    add_setting("privacy_and_records", "data_retention_days", "USER_AFTER_ADMIN_ALLOWED", True) # Always visible
    add_setting("privacy_and_records", "broadcast_individual_deposit_receipts", "USER_AFTER_ADMIN_ALLOWED", vis_settings.vis_broadcast_individual_deposit_receipts)
    add_setting("privacy_and_records", "send_daily_group_summaries", "USER_AFTER_ADMIN_ALLOWED", vis_settings.vis_send_daily_group_summaries)
    
    # --- PERSONAL PREFERENCES (Admin & User - always viewable and editable by the individual) ---
    add_setting("personal_preferences", "my_payout_destination", "ADMIN_AND_USER", True)
    add_setting("personal_preferences", "auto_pay_my_turn", "ADMIN_AND_USER", True)
    add_setting("personal_preferences", "request_turn_swap", "ADMIN_AND_USER", True)
    add_setting("personal_preferences", "media_visibility", "ADMIN_AND_USER", True)
    add_setting("personal_preferences", "encryption_status", "ADMIN_AND_USER", True)
    add_setting("personal_preferences", "chat_lock", "ADMIN_AND_USER", True)
    add_setting("personal_preferences", "mute_notifications", "ADMIN_AND_USER", True)
    
    return {
        "status": "success",
        "data": manifest
    }
