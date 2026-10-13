from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, BigInteger
from app.utils.time.now_epoch_ms import now_epoch_ms

def utc_now():
    return now_epoch_ms()

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
    
    updated_at: int = Field(default_factory=now_epoch_ms, sa_column=Column(BigInteger))
