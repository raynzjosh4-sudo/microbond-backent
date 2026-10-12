"""add_welfare_fund_and_event_committee_tables

Revision ID: 6307ba3d4766
Revises: ace1219c1046
Create Date: 2026-10-11 20:04:30

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '6307ba3d4766'
down_revision: Union[str, Sequence[str], None] = 'ace1219c1046'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create welfarefundconfig, welfarefundoperationalsettings,
    eventcommitteeconfig, and eventcommitteeoperationalsettings tables."""

    # 1. welfarefundconfig
    op.create_table(
        'welfarefundconfig',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('group_id', sa.String(), nullable=False),
        sa.Column('contribution_amount', sa.BigInteger(), nullable=False),
        sa.Column('collection_frequency_days', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('waiting_period_days', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('max_claim_amount_per_incident', sa.BigInteger(), nullable=False),
        sa.Column('annual_claim_limit_per_member', sa.BigInteger(), nullable=False),
        sa.Column('payout_destination_type', sa.String(), nullable=False, server_default='MEMBER_ACCOUNT'),
        sa.Column('requires_documentary_evidence', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('claim_approval_policy', sa.String(), nullable=False, server_default='MAJORITY_VOTE'),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['group.group_id'], name='welfarefundconfig_group_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='welfarefundconfig_pkey')
    )
    op.create_index('ix_welfarefundconfig_group_id', 'welfarefundconfig', ['group_id'], unique=True)

    # 2. welfarefundoperationalsettings
    op.create_table(
        'welfarefundoperationalsettings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('group_id', sa.String(), nullable=False),
        sa.Column('minimum_reserve_balance', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('approval_timeout_hours', sa.Integer(), nullable=False, server_default='48'),
        sa.Column('missed_payment_action', sa.String(), nullable=False, server_default='SUSPEND_CLAIM_RIGHTS'),
        sa.Column('enable_late_fees', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('allow_annual_dividend_split', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('current_balance', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_collected', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_paid_out', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['group.group_id'], name='welfarefundoperationalsettings_group_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='welfarefundoperationalsettings_pkey')
    )
    op.create_index('ix_welfarefundoperationalsettings_group_id', 'welfarefundoperationalsettings', ['group_id'], unique=True)

    # 3. eventcommitteeconfig
    op.create_table(
        'eventcommitteeconfig',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('group_id', sa.String(), nullable=False),
        sa.Column('event_target_budget', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('event_date', sa.BigInteger(), nullable=False),
        sa.Column('collection_deadline', sa.BigInteger(), nullable=False),
        sa.Column('payout_destination_type', sa.String(), nullable=False, server_default='VERIFIED_VENDORS_ONLY'),
        sa.Column('spending_signoff_policy', sa.String(), nullable=False, server_default='CHAIRMAN_ONLY'),
        sa.Column('excess_funds_action', sa.String(), nullable=False, server_default='PROPORTIONAL_REFUND'),
        sa.Column('require_invoice_upload', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['group.group_id'], name='eventcommitteeconfig_group_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='eventcommitteeconfig_pkey')
    )
    op.create_index('ix_eventcommitteeconfig_group_id', 'eventcommitteeconfig', ['group_id'], unique=True)

    # 4. eventcommitteeoperationalsettings
    op.create_table(
        'eventcommitteeoperationalsettings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('group_id', sa.String(), nullable=False),
        sa.Column('allow_overfunding', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('track_pledges', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('minimum_contribution_amount', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('member_quota_amount', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('allow_guest_deposits', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('allow_partial_disbursements', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('signoff_trustee_user_ids', sa.String(), nullable=False, server_default='[]'),
        sa.Column('current_balance', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_pledged', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_disbursed', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['group.group_id'], name='eventcommitteeoperationalsettings_group_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='eventcommitteeoperationalsettings_pkey')
    )
    op.create_index('ix_eventcommitteeoperationalsettings_group_id', 'eventcommitteeoperationalsettings', ['group_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_eventcommitteeoperationalsettings_group_id', table_name='eventcommitteeoperationalsettings')
    op.drop_table('eventcommitteeoperationalsettings')
    op.drop_index('ix_eventcommitteeconfig_group_id', table_name='eventcommitteeconfig')
    op.drop_table('eventcommitteeconfig')
    op.drop_index('ix_welfarefundoperationalsettings_group_id', table_name='welfarefundoperationalsettings')
    op.drop_table('welfarefundoperationalsettings')
    op.drop_index('ix_welfarefundconfig_group_id', table_name='welfarefundconfig')
    op.drop_table('welfarefundconfig')
