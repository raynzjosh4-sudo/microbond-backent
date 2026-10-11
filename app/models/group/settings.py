from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
from datetime import datetime, timezone

def utc_now():
    return int(datetime.now(timezone.utc).timestamp() * 1000)

class GroupFinancialSettings(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)
    
    # Payout Rules
    payout_selection_strategy: str = Field(default="Admin-Assigned")
    enforce_payout_holds: bool = Field(default=True)
    allow_substitute_members: bool = Field(default=False)
    max_pending_payouts: int = Field(default=2, description="How many payouts can be pending/queued at once")
    
    # Penalties & Grace Period
    enable_late_fees: bool = Field(default=True)
    late_fee_amount: float = Field(default=10000.0)
    late_fee_frequency: str = Field(default="Per day")
    enable_grace_period: bool = Field(default=True)
    grace_period_hours: int = Field(default=24)
    arrears_policy: str = Field(default="Deduct from next payout")
    
    # Payout Limits
    max_payout_active: bool = Field(default=True)
    max_payout_limit: str = Field(default="10,000,000 UGX")
    reserve_fund_percentage: float = Field(default=0.0)
    
    # Escrow & Timelocks
    enable_escrow: bool = Field(default=True)
    escrow_release_condition: str = Field(default="Upon unanimous approval")
    enable_timelock: bool = Field(default=True)
    timelock_duration_hours: int = Field(default=24)
    
    updated_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))

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
    
    # Group Permissions (Admins)
    admins_must_approve_new_members: bool = Field(default=False)
    requires_admin_approval: bool = Field(default=False)
    
    updated_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))

class GroupCommunicationSettings(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)
    
    # Transaction Messages
    broadcast_individual_deposit_receipts: bool = Field(default=True)
    announce_payout_updates: bool = Field(default=True)
    show_transfer_receipts: bool = Field(default=True)
    announce_admin_transactions: bool = Field(default=True)
    
    # Reminders & Reports
    send_daily_group_summaries: bool = Field(default=True)
    daily_summary_time: str = Field(default="18:00")
    post_weekly_financial_reports: bool = Field(default=True)
    weekly_report_day: str = Field(default="Friday")
    weekly_report_time: str = Field(default="17:00")
    send_deposit_due_prompts: bool = Field(default=True)
    
    # Milestones & Security
    share_financial_snapshots: bool = Field(default=True)
    announce_system_events: bool = Field(default=True)
    post_security_rule_updates: bool = Field(default=True)
    post_group_approval_polls: bool = Field(default=True)
    notify_important_rule_changes: bool = Field(default=True)
    
    # Records & Cleanup
    data_retention_days: int = Field(default=730, description="Number of days to keep data")
    chat_history_cleanup_days: int = Field(default=90) # auto-delete older than
    preserve_financial_records: bool = Field(default=True)
    
    # Audit Ledger Delivery & Financial Statements
    enable_automated_audit_dispatch: bool = Field(default=True, description="Enables scheduled or on-demand dispatch of audit ledgers via email")
    audit_report_recipient_email: Optional[str] = Field(default=None, description="Designated email for receiving group statements/audits")
    dispatch_monthly_compliance_statement: bool = Field(default=True, description="Send automated monthly compliance statements to admin/treasurer")
    export_file_format: str = Field(default="PDF", description="Preferred export format: PDF or CSV")
    
    updated_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))

class GroupVisibilitySettings(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)
    
    # Advanced Group Privacy
    hide_total_group_balance: bool = Field(default=False)
    hide_member_contact_info: bool = Field(default=True)
    invite_only_discoverability: bool = Field(default=True)
    
    # Financial Report Visibility
    vis_report_expected_revenue: bool = Field(default=False)
    vis_report_actual_collection: bool = Field(default=False)
    vis_report_deficit: bool = Field(default=False)
    vis_report_reserve_fund: bool = Field(default=False)
    vis_report_escrow_holds: bool = Field(default=False)
    
    # Member Visibility (Toggles to show/hide admin settings from members)
    vis_manage_payout_order: bool = Field(default=False)
    vis_late_fee_penalties: bool = Field(default=False)
    vis_grace_period_window: bool = Field(default=False)
    vis_enforce_payout_holds: bool = Field(default=False)
    vis_substitute_member_allowance: bool = Field(default=False)
    
    vis_multi_signature_roster: bool = Field(default=False)
    vis_active_audit_status: bool = Field(default=False)
    vis_approval_quorum: bool = Field(default=False)
    vis_pending_payout_queue: bool = Field(default=False)
    vis_require_multi_signature: bool = Field(default=False)
    vis_time_lock_disbursals: bool = Field(default=False)
    
    vis_guarantor_required: bool = Field(default=False)
    
    vis_contribution_reminder_schedule: bool = Field(default=False)
    vis_liquidity_buffer_coverage: bool = Field(default=False)
    vis_late_fee_escalation: bool = Field(default=False)
    
    vis_download_official_statement: bool = Field(default=True)
    vis_chat_history_cleanup: bool = Field(default=True)
    
    vis_broadcast_individual_deposit_receipts: bool = Field(default=True)
    vis_announce_payout_updates: bool = Field(default=True)
    vis_show_transfer_receipts: bool = Field(default=True)
    vis_announce_admin_transactions: bool = Field(default=True)
    
    vis_send_daily_group_summaries: bool = Field(default=True)
    vis_post_weekly_financial_reports: bool = Field(default=True)
    vis_send_deposit_due_prompts: bool = Field(default=True)
    vis_daily_summary_time: bool = Field(default=True)
    vis_weekly_report_day: bool = Field(default=True)
    
    vis_share_financial_snapshots: bool = Field(default=True)
    vis_announce_system_events: bool = Field(default=True)
    vis_post_security_rule_updates: bool = Field(default=True)
    vis_post_group_approval_polls: bool = Field(default=True)
    vis_notify_important_rule_changes: bool = Field(default=True)
    
    updated_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))
