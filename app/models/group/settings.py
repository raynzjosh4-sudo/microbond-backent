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
    
    # Fund Stability, Liquidity & Reminders
    liquidity_buffer_percentage: float = Field(default=10.0, description="Percentage of group funds reserved as liquid buffer")
    enable_late_fee_escalation: bool = Field(default=True, description="Escalate late penalty fees each cycle a payment remains missed")
    contribution_reminder_days_before: int = Field(default=2, description="Days before due date to schedule reminder")
    auto_debit_consent_required: bool = Field(default=True, description="Permit automatic collection only from members who opted in")
    emergency_contact_name: Optional[str] = Field(default=None, description="Name of contact for urgent payment issues")
    emergency_contact_phone: Optional[str] = Field(default=None, description="Phone of contact for urgent payment issues")
    enable_sms_call_reminders: bool = Field(default=True, description="Send automated SMS and phone call reminders")
    
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
    send_dues_due_prompts: bool = Field(default=True, description="Prompt members when dues subscription cycles are approaching due date")
    send_loan_due_prompts: bool = Field(default=True, description="Prompt members when loan repayment deadlines approach")
    broadcast_individual_dues_receipts: bool = Field(default=True, description="Broadcast individual dues receipts in group chat")
    broadcast_individual_loan_receipts: bool = Field(default=True, description="Broadcast individual loan repayment receipts in group chat")
    announce_dues_adjustment_updates: bool = Field(default=True, description="Post notice when admin adjusts dues rates or policies")
    announce_loan_disbursement_updates: bool = Field(default=True, description="Post notice when loan disbursement occurs")
    
    # Milestones & Security
    share_financial_snapshots: bool = Field(default=True)
    announce_system_events: bool = Field(default=True)
    post_security_rule_updates: bool = Field(default=True)
    post_group_approval_polls: bool = Field(default=True)
    post_loan_approval_polls: bool = Field(default=True, description="Post loan review and voting polls in chat")
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
    
    # Dues & Loan Administration Visibility
    vis_dues_schedule: bool = Field(default=False, description="Hide/show dues amount and frequency from members")
    vis_allow_installments: bool = Field(default=False, description="Hide/show allow installments toggle from members")
    vis_arrears_policy: bool = Field(default=False, description="Hide/show arrears policy details from members")
    vis_fee_exemptions: bool = Field(default=False, description="Hide/show fee exemptions management from members")
    vis_interest_rates: bool = Field(default=False, description="Hide/show investment interest rates from members")
    vis_loan_guarantor_rules: bool = Field(default=False, description="Hide/show loan guarantor rules from members")
    vis_max_borrowing_limit: bool = Field(default=False, description="Hide/show maximum borrowing limit from members")
    vis_early_repayment_discount: bool = Field(default=False, description="Hide/show early repayment discount from members")
    vis_new_share_issuance: bool = Field(default=False, description="Hide/show new share issuance rules from members")
    vis_default_asset_seizure: bool = Field(default=False, description="Hide/show default asset seizure recovery actions from members")

    vis_multi_signature_roster: bool = Field(default=False)
    vis_active_audit_status: bool = Field(default=False)
    vis_approval_quorum: bool = Field(default=False)
    vis_pending_payout_queue: bool = Field(default=False)
    vis_pending_dues_adjustments: bool = Field(default=False, description="Hide/show pending dues adjustments from members")
    vis_pending_loans: bool = Field(default=False, description="Hide/show pending loans queue from members")
    vis_require_multi_signature: bool = Field(default=False)
    vis_time_lock_disbursals: bool = Field(default=False)
    
    vis_guarantor_required: bool = Field(default=False)
    
    vis_contribution_reminder_schedule: bool = Field(default=False)
    vis_liquidity_buffer_coverage: bool = Field(default=False)
    vis_late_fee_escalation: bool = Field(default=False)
    vis_auto_debit_consent: bool = Field(default=False, description="Hide/show auto-debit consent toggle from members")
    vis_emergency_contact: bool = Field(default=False, description="Hide/show emergency contact setting from members")
    vis_sms_call_reminders: bool = Field(default=False, description="Hide/show SMS/call reminders toggle from members")
    
    vis_download_official_statement: bool = Field(default=True)
    vis_chat_history_cleanup: bool = Field(default=True)
    
    vis_broadcast_individual_deposit_receipts: bool = Field(default=True)
    vis_broadcast_individual_dues_receipts: bool = Field(default=True)
    vis_broadcast_individual_loan_receipts: bool = Field(default=True, description="Hide/show loan repayment receipts in chat")
    vis_announce_payout_updates: bool = Field(default=True)
    vis_announce_dues_adjustment_updates: bool = Field(default=True)
    vis_announce_loan_disbursement_updates: bool = Field(default=True, description="Hide/show loan disbursement updates in chat")
    vis_show_transfer_receipts: bool = Field(default=True)
    vis_announce_admin_transactions: bool = Field(default=True)
    
    vis_send_daily_group_summaries: bool = Field(default=True)
    vis_post_weekly_financial_reports: bool = Field(default=True)
    vis_send_deposit_due_prompts: bool = Field(default=True)
    vis_send_dues_due_prompts: bool = Field(default=True)
    vis_send_loan_due_prompts: bool = Field(default=True, description="Hide/show loan repayment due prompts")
    vis_daily_summary_time: bool = Field(default=True)
    vis_weekly_report_day: bool = Field(default=True)
    
    vis_share_financial_snapshots: bool = Field(default=True)
    vis_announce_system_events: bool = Field(default=True)
    vis_post_security_rule_updates: bool = Field(default=True)
    vis_post_group_approval_polls: bool = Field(default=True)
    vis_post_loan_approval_polls: bool = Field(default=True, description="Hide/show loan approval polls")
    vis_notify_important_rule_changes: bool = Field(default=True)
    notify_important_rule_changes: bool = Field(default=True)
    
    updated_at: int = Field(default_factory=utc_now, sa_column=Column(BigInteger))

