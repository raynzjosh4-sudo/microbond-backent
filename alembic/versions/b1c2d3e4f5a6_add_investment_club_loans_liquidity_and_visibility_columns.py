"""add_investment_club_loans_liquidity_and_visibility_columns

Revision ID: b1c2d3e4f5a6
Revises: a937dc1290fe
Create Date: 2026-10-12 03:00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, Sequence[str], None] = 'a937dc1290fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. investmentclubloan table ─────────────────────────────────────────────
    op.create_table(
        'investmentclubloan',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('group_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('principal_amount', sa.BigInteger(), nullable=False),
        sa.Column('interest_rate_pct', sa.Float(), nullable=False, server_default='10.0'),
        sa.Column('total_due_amount', sa.BigInteger(), nullable=False),
        sa.Column('amount_repaid', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('early_discount_applied', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(), nullable=False, server_default='PENDING'),
        sa.Column('guarantors_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('due_date', sa.BigInteger(), nullable=False),
        sa.Column('disbursed_at', sa.BigInteger(), nullable=True),
        sa.Column('settled_at', sa.BigInteger(), nullable=True),
        sa.Column('approved_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['group.group_id'], name='investmentclubloan_group_id_fkey'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='investmentclubloan_user_id_fkey'),
        sa.ForeignKeyConstraint(['approved_by'], ['user.id'], name='investmentclubloan_approved_by_fkey'),
        sa.PrimaryKeyConstraint('id', name='investmentclubloan_pkey')
    )
    op.create_index('ix_investmentclubloan_group_id', 'investmentclubloan', ['group_id'], unique=False)
    op.create_index('ix_investmentclubloan_user_id', 'investmentclubloan', ['user_id'], unique=False)

    # ── 2. investmentcluboperationalsettings new columns ────────────────────────
    op.add_column('investmentcluboperationalsettings',
        sa.Column('interest_rate_mode', sa.String(), nullable=False, server_default='GROUP_VOTE'))
    op.add_column('investmentcluboperationalsettings',
        sa.Column('fixed_interest_rate_pct', sa.Float(), nullable=False, server_default='10.0'))
    op.add_column('investmentcluboperationalsettings',
        sa.Column('require_loan_guarantors', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('investmentcluboperationalsettings',
        sa.Column('min_loan_guarantors', sa.Integer(), nullable=False, server_default='2'))
    op.add_column('investmentcluboperationalsettings',
        sa.Column('max_borrowing_limit', sa.BigInteger(), nullable=False, server_default='2000000'))
    op.add_column('investmentcluboperationalsettings',
        sa.Column('early_repayment_discount_pct', sa.Float(), nullable=False, server_default='2.0'))
    op.add_column('investmentcluboperationalsettings',
        sa.Column('new_share_issuance_mode', sa.String(), nullable=False, server_default='MEMBER_APPROVAL'))
    op.add_column('investmentcluboperationalsettings',
        sa.Column('default_recovery_action', sa.String(), nullable=False, server_default='COLLATERAL_SEIZURE'))
    op.add_column('investmentcluboperationalsettings',
        sa.Column('contribution_reminder_days_before', sa.Integer(), nullable=False, server_default='2'))
    op.add_column('investmentcluboperationalsettings',
        sa.Column('auto_debit_consent_required', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('investmentcluboperationalsettings',
        sa.Column('emergency_contact_name', sa.String(), nullable=True))
    op.add_column('investmentcluboperationalsettings',
        sa.Column('emergency_contact_phone', sa.String(), nullable=True))
    op.add_column('investmentcluboperationalsettings',
        sa.Column('liquidity_buffer_coverage_pct', sa.Integer(), nullable=False, server_default='10'))
    op.add_column('investmentcluboperationalsettings',
        sa.Column('enable_late_fee_escalation', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('investmentcluboperationalsettings',
        sa.Column('enable_sms_call_reminders', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('investmentcluboperationalsettings',
        sa.Column('active_loans_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('investmentcluboperationalsettings',
        sa.Column('total_loans_disbursed', sa.BigInteger(), nullable=False, server_default='0'))

    # ── 3. groupfinancialsettings new columns ───────────────────────────────────
    op.add_column('groupfinancialsettings',
        sa.Column('liquidity_buffer_percentage', sa.Float(), nullable=False, server_default='10.0'))
    op.add_column('groupfinancialsettings',
        sa.Column('enable_late_fee_escalation', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('groupfinancialsettings',
        sa.Column('contribution_reminder_days_before', sa.Integer(), nullable=False, server_default='2'))
    op.add_column('groupfinancialsettings',
        sa.Column('auto_debit_consent_required', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('groupfinancialsettings',
        sa.Column('emergency_contact_name', sa.String(), nullable=True))
    op.add_column('groupfinancialsettings',
        sa.Column('emergency_contact_phone', sa.String(), nullable=True))
    op.add_column('groupfinancialsettings',
        sa.Column('enable_sms_call_reminders', sa.Boolean(), nullable=False, server_default='true'))

    # ── 4. groupvisibilitysettings new columns ──────────────────────────────────
    # Investment-club rules visibility toggles
    op.add_column('groupvisibilitysettings',
        sa.Column('vis_interest_rates', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('groupvisibilitysettings',
        sa.Column('vis_loan_guarantor_rules', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('groupvisibilitysettings',
        sa.Column('vis_max_borrowing_limit', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('groupvisibilitysettings',
        sa.Column('vis_early_repayment_discount', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('groupvisibilitysettings',
        sa.Column('vis_new_share_issuance', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('groupvisibilitysettings',
        sa.Column('vis_default_asset_seizure', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('groupvisibilitysettings',
        sa.Column('vis_pending_loans', sa.Boolean(), nullable=False, server_default='false'))
    # Liquidity & reminders visibility toggles
    op.add_column('groupvisibilitysettings',
        sa.Column('vis_auto_debit_consent', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('groupvisibilitysettings',
        sa.Column('vis_emergency_contact', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('groupvisibilitysettings',
        sa.Column('vis_sms_call_reminders', sa.Boolean(), nullable=False, server_default='false'))
    # Loan messages / milestones visibility toggles
    op.add_column('groupvisibilitysettings',
        sa.Column('vis_send_loan_due_prompts', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('groupvisibilitysettings',
        sa.Column('vis_broadcast_individual_loan_receipts', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('groupvisibilitysettings',
        sa.Column('vis_announce_loan_disbursement_updates', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('groupvisibilitysettings',
        sa.Column('vis_post_loan_approval_polls', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('groupvisibilitysettings',
        sa.Column('vis_notify_important_rule_changes', sa.Boolean(), nullable=False, server_default='true'))

    # ── 5. groupcommunicationsettings new columns ───────────────────────────────
    op.add_column('groupcommunicationsettings',
        sa.Column('send_loan_due_prompts', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('groupcommunicationsettings',
        sa.Column('broadcast_individual_loan_receipts', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('groupcommunicationsettings',
        sa.Column('announce_loan_disbursement_updates', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('groupcommunicationsettings',
        sa.Column('post_loan_approval_polls', sa.Boolean(), nullable=False, server_default='true'))

    # ── 6. groupmembership SMS & Email reminder columns ─────────────────────────
    op.add_column('groupmembership',
        sa.Column('sms_reminders_opted_in', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('groupmembership',
        sa.Column('sms_reminder_hours_before', sa.Integer(), nullable=False, server_default='24'))
    op.add_column('groupmembership',
        sa.Column('sms_fee_acknowledged', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('groupmembership',
        sa.Column('pending_sms_fee_ugx', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('groupmembership',
        sa.Column('email_reminders_opted_in', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('groupmembership',
        sa.Column('email_reminder_hours_before', sa.Integer(), nullable=False, server_default='24'))


def downgrade() -> None:
    # ── 6. Drop GroupMembership reminder columns ────────────────────────────────
    op.drop_column('groupmembership', 'email_reminder_hours_before')
    op.drop_column('groupmembership', 'email_reminders_opted_in')
    op.drop_column('groupmembership', 'pending_sms_fee_ugx')
    op.drop_column('groupmembership', 'sms_fee_acknowledged')
    op.drop_column('groupmembership', 'sms_reminder_hours_before')
    op.drop_column('groupmembership', 'sms_reminders_opted_in')

    # ── 5. Drop communication fields ────────────────────────────────────────────
    op.drop_column('groupcommunicationsettings', 'post_loan_approval_polls')
    op.drop_column('groupcommunicationsettings', 'announce_loan_disbursement_updates')
    op.drop_column('groupcommunicationsettings', 'broadcast_individual_loan_receipts')
    op.drop_column('groupcommunicationsettings', 'send_loan_due_prompts')

    # ── 4. Drop visibility columns ──────────────────────────────────────────────
    op.drop_column('groupvisibilitysettings', 'vis_notify_important_rule_changes')
    op.drop_column('groupvisibilitysettings', 'vis_post_loan_approval_polls')
    op.drop_column('groupvisibilitysettings', 'vis_announce_loan_disbursement_updates')
    op.drop_column('groupvisibilitysettings', 'vis_broadcast_individual_loan_receipts')
    op.drop_column('groupvisibilitysettings', 'vis_send_loan_due_prompts')
    op.drop_column('groupvisibilitysettings', 'vis_sms_call_reminders')
    op.drop_column('groupvisibilitysettings', 'vis_emergency_contact')
    op.drop_column('groupvisibilitysettings', 'vis_auto_debit_consent')
    op.drop_column('groupvisibilitysettings', 'vis_pending_loans')
    op.drop_column('groupvisibilitysettings', 'vis_default_asset_seizure')
    op.drop_column('groupvisibilitysettings', 'vis_new_share_issuance')
    op.drop_column('groupvisibilitysettings', 'vis_early_repayment_discount')
    op.drop_column('groupvisibilitysettings', 'vis_max_borrowing_limit')
    op.drop_column('groupvisibilitysettings', 'vis_loan_guarantor_rules')
    op.drop_column('groupvisibilitysettings', 'vis_interest_rates')

    # ── 3. Drop groupfinancialsettings columns ──────────────────────────────────
    op.drop_column('groupfinancialsettings', 'enable_sms_call_reminders')
    op.drop_column('groupfinancialsettings', 'emergency_contact_phone')
    op.drop_column('groupfinancialsettings', 'emergency_contact_name')
    op.drop_column('groupfinancialsettings', 'auto_debit_consent_required')
    op.drop_column('groupfinancialsettings', 'contribution_reminder_days_before')
    op.drop_column('groupfinancialsettings', 'enable_late_fee_escalation')
    op.drop_column('groupfinancialsettings', 'liquidity_buffer_percentage')

    # ── 2. Drop investmentcluboperationalsettings columns ───────────────────────
    op.drop_column('investmentcluboperationalsettings', 'total_loans_disbursed')
    op.drop_column('investmentcluboperationalsettings', 'active_loans_count')
    op.drop_column('investmentcluboperationalsettings', 'enable_sms_call_reminders')
    op.drop_column('investmentcluboperationalsettings', 'enable_late_fee_escalation')
    op.drop_column('investmentcluboperationalsettings', 'liquidity_buffer_coverage_pct')
    op.drop_column('investmentcluboperationalsettings', 'emergency_contact_phone')
    op.drop_column('investmentcluboperationalsettings', 'emergency_contact_name')
    op.drop_column('investmentcluboperationalsettings', 'auto_debit_consent_required')
    op.drop_column('investmentcluboperationalsettings', 'contribution_reminder_days_before')
    op.drop_column('investmentcluboperationalsettings', 'default_recovery_action')
    op.drop_column('investmentcluboperationalsettings', 'new_share_issuance_mode')
    op.drop_column('investmentcluboperationalsettings', 'early_repayment_discount_pct')
    op.drop_column('investmentcluboperationalsettings', 'max_borrowing_limit')
    op.drop_column('investmentcluboperationalsettings', 'min_loan_guarantors')
    op.drop_column('investmentcluboperationalsettings', 'require_loan_guarantors')
    op.drop_column('investmentcluboperationalsettings', 'fixed_interest_rate_pct')
    op.drop_column('investmentcluboperationalsettings', 'interest_rate_mode')

    # ── 1. Drop investmentclubloan table ────────────────────────────────────────
    op.drop_index('ix_investmentclubloan_user_id', table_name='investmentclubloan')
    op.drop_index('ix_investmentclubloan_group_id', table_name='investmentclubloan')
    op.drop_table('investmentclubloan')
