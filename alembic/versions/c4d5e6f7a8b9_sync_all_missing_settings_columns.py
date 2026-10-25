"""Sync all missing settings columns for communication, visibility, governance, and rotating details

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-10-25 08:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Columns for groupcommunicationsettings
    comm_cols = [
        ('send_dues_due_prompts', sa.Column('send_dues_due_prompts', sa.Boolean(), nullable=False, server_default='true')),
        ('send_loan_due_prompts', sa.Column('send_loan_due_prompts', sa.Boolean(), nullable=False, server_default='true')),
        ('broadcast_individual_dues_receipts', sa.Column('broadcast_individual_dues_receipts', sa.Boolean(), nullable=False, server_default='true')),
        ('broadcast_individual_loan_receipts', sa.Column('broadcast_individual_loan_receipts', sa.Boolean(), nullable=False, server_default='true')),
        ('announce_dues_adjustment_updates', sa.Column('announce_dues_adjustment_updates', sa.Boolean(), nullable=False, server_default='true')),
        ('announce_loan_disbursement_updates', sa.Column('announce_loan_disbursement_updates', sa.Boolean(), nullable=False, server_default='true')),
        ('post_loan_approval_polls', sa.Column('post_loan_approval_polls', sa.Boolean(), nullable=False, server_default='true')),
        ('enable_automated_audit_dispatch', sa.Column('enable_automated_audit_dispatch', sa.Boolean(), nullable=False, server_default='true')),
        ('audit_report_recipient_email', sa.Column('audit_report_recipient_email', sqlmodel.sql.sqltypes.AutoString(), nullable=True)),
        ('dispatch_monthly_compliance_statement', sa.Column('dispatch_monthly_compliance_statement', sa.Boolean(), nullable=False, server_default='true')),
        ('export_file_format', sa.Column('export_file_format', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='PDF')),
    ]

    for col_name, col_def in comm_cols:
        res = conn.execute(sa.text(f"""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'groupcommunicationsettings'
            AND column_name = '{col_name}'
        """))
        if res.fetchone() is None:
            op.add_column('groupcommunicationsettings', col_def)

    # Columns for groupvisibilitysettings
    vis_cols = [
        ('vis_member_total_savings', sa.Column('vis_member_total_savings', sa.Boolean(), nullable=False, server_default='true')),
        ('vis_dues_schedule', sa.Column('vis_dues_schedule', sa.Boolean(), nullable=False, server_default='false')),
        ('vis_allow_installments', sa.Column('vis_allow_installments', sa.Boolean(), nullable=False, server_default='false')),
        ('vis_arrears_policy', sa.Column('vis_arrears_policy', sa.Boolean(), nullable=False, server_default='false')),
        ('vis_fee_exemptions', sa.Column('vis_fee_exemptions', sa.Boolean(), nullable=False, server_default='false')),
        ('vis_interest_rates', sa.Column('vis_interest_rates', sa.Boolean(), nullable=False, server_default='false')),
        ('vis_loan_guarantor_rules', sa.Column('vis_loan_guarantor_rules', sa.Boolean(), nullable=False, server_default='false')),
        ('vis_max_borrowing_limit', sa.Column('vis_max_borrowing_limit', sa.Boolean(), nullable=False, server_default='false')),
        ('vis_early_repayment_discount', sa.Column('vis_early_repayment_discount', sa.Boolean(), nullable=False, server_default='false')),
        ('vis_new_share_issuance', sa.Column('vis_new_share_issuance', sa.Boolean(), nullable=False, server_default='false')),
        ('vis_default_asset_seizure', sa.Column('vis_default_asset_seizure', sa.Boolean(), nullable=False, server_default='false')),
        ('vis_pending_dues_adjustments', sa.Column('vis_pending_dues_adjustments', sa.Boolean(), nullable=False, server_default='false')),
        ('vis_pending_loans', sa.Column('vis_pending_loans', sa.Boolean(), nullable=False, server_default='false')),
        ('vis_auto_debit_consent', sa.Column('vis_auto_debit_consent', sa.Boolean(), nullable=False, server_default='false')),
        ('vis_emergency_contact', sa.Column('vis_emergency_contact', sa.Boolean(), nullable=False, server_default='false')),
        ('vis_sms_call_reminders', sa.Column('vis_sms_call_reminders', sa.Boolean(), nullable=False, server_default='false')),
        ('vis_broadcast_individual_dues_receipts', sa.Column('vis_broadcast_individual_dues_receipts', sa.Boolean(), nullable=False, server_default='true')),
        ('vis_broadcast_individual_loan_receipts', sa.Column('vis_broadcast_individual_loan_receipts', sa.Boolean(), nullable=False, server_default='true')),
        ('vis_announce_dues_adjustment_updates', sa.Column('vis_announce_dues_adjustment_updates', sa.Boolean(), nullable=False, server_default='true')),
        ('vis_announce_loan_disbursement_updates', sa.Column('vis_announce_loan_disbursement_updates', sa.Boolean(), nullable=False, server_default='true')),
        ('vis_send_dues_due_prompts', sa.Column('vis_send_dues_due_prompts', sa.Boolean(), nullable=False, server_default='true')),
        ('vis_send_loan_due_prompts', sa.Column('vis_send_loan_due_prompts', sa.Boolean(), nullable=False, server_default='true')),
        ('vis_post_loan_approval_polls', sa.Column('vis_post_loan_approval_polls', sa.Boolean(), nullable=False, server_default='true')),
        ('notify_important_rule_changes', sa.Column('notify_important_rule_changes', sa.Boolean(), nullable=False, server_default='true')),
    ]

    for col_name, col_def in vis_cols:
        res = conn.execute(sa.text(f"""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'groupvisibilitysettings'
            AND column_name = '{col_name}'
        """))
        if res.fetchone() is None:
            op.add_column('groupvisibilitysettings', col_def)


def downgrade() -> None:
    pass
