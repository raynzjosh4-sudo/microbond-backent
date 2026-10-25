from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class GroupGovernanceSettings(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)
    
    # Auditing & Charter
    is_audit_active: bool = Field(default=False)
    group_charter_url: Optional[str] = Field(default=None, description="URL to the official Group Charter PDF/Document")
    
    # Signatures & Approvals
    require_multi_signature: bool = Field(default=True)
    multi_sig_required_approvals: int = Field(default=3)
    approval_strategy: str = Field(default="Majority Vote")
    quorum_percentage: str = Field(default="60%")
    
    # Deadlock / Hostage Protection (Time-Locked Quorum Decay)
    enable_quorum_decay: bool = Field(default=True)
    quorum_decay_hours: int = Field(default=48, description="Hours before required approvals start dropping")
    quorum_decay_minimum_approvals: int = Field(default=2, description="The absolute floor that quorum can decay to")
    
    # Trust & Members
    require_guarantors: bool = Field(default=False)
    guarantor_count: int = Field(default=2)
    minimum_trust_score: Optional[int] = Field(default=None)
    
    # Group Permissions (Members)
    members_can_edit_settings: bool = Field(default=True)
    members_can_send_messages: bool = Field(default=True)
    members_can_invite_via_link: bool = Field(default=False)
    members_can_manage_payout_roster: bool = Field(default=False)
    allow_turn_swaps: bool = Field(default=True)
    turn_swap_approval_mode: str = Field(default="MUTUAL_CONSENT", description="MUTUAL_CONSENT or ADMIN_APPROVAL_REQUIRED")
    
    # Group Permissions (Admins)
    admins_must_approve_new_members: bool = Field(default=False)
    requires_admin_approval: bool = Field(default=False)
    
    updated_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
