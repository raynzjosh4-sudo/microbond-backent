from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

class GroupVisibilitySettings(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True, unique=True)
    
    # Advanced Group Privacy
    hide_total_group_balance: bool = Field(default=False)
    hide_member_contact_info: bool = Field(default=True)
    invite_only_discoverability: bool = Field(default=True)
    deposit_widget_visibility: str = Field(default="ALL_MEMBERS", description="Who can view deposit widget: ALL_MEMBERS, ADMIN_ONLY, ADMIN_AND_TREASURER")
    vis_member_total_savings: bool = Field(default=True, description="Allow members to view their savings / total contributed")
    
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
    
    updated_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
