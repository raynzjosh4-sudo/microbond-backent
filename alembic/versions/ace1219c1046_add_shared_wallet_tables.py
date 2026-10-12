"""add_shared_wallet_tables

Revision ID: ace1219c1046
Revises: 90bf9550c526
Create Date: 2026-10-11 19:43:55.049208

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'ace1219c1046'
down_revision: Union[str, Sequence[str], None] = '90bf9550c526'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create sharedwalletconfig and sharedwalletoperationalsettings tables."""
    # 1. sharedwalletconfig
    op.create_table(
        'sharedwalletconfig',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('group_id', sa.String(), nullable=False),
        sa.Column('replenishment_mode', sa.String(), nullable=False, server_default='FLEXIBLE'),
        sa.Column('member_quota_amount', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('collection_frequency_days', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('spending_signoff_policy', sa.String(), nullable=False, server_default='ADMIN_ONLY'),
        sa.Column('exit_payout_rule', sa.String(), nullable=False, server_default='PROPORTIONAL_REMAINING'),
        sa.Column('track_individual_contributions', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('minimum_kyc_tier', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['group.group_id'], name='sharedwalletconfig_group_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='sharedwalletconfig_pkey')
    )
    op.create_index('ix_sharedwalletconfig_group_id', 'sharedwalletconfig', ['group_id'], unique=True)

    # 2. sharedwalletoperationalsettings
    op.create_table(
        'sharedwalletoperationalsettings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('group_id', sa.String(), nullable=False),
        sa.Column('minimum_balance_floor', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('target_budget_limit', sa.BigInteger(), nullable=True),
        sa.Column('auto_approve_threshold', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('approval_timeout_hours', sa.Integer(), nullable=False, server_default='24'),
        sa.Column('timelock_duration_hours', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('daily_spending_cap', sa.BigInteger(), nullable=True),
        sa.Column('per_transaction_cap', sa.BigInteger(), nullable=True),
        sa.Column('allowed_disbursement_types', sa.String(), nullable=False, server_default='["MEMBER_ACCOUNTS", "EXTERNAL_PAYEES"]'),
        sa.Column('current_balance', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_deposited', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_spent', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['group.group_id'], name='sharedwalletoperationalsettings_group_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='sharedwalletoperationalsettings_pkey')
    )
    op.create_index('ix_sharedwalletoperationalsettings_group_id', 'sharedwalletoperationalsettings', ['group_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_sharedwalletoperationalsettings_group_id', table_name='sharedwalletoperationalsettings')
    op.drop_table('sharedwalletoperationalsettings')
    op.drop_index('ix_sharedwalletconfig_group_id', table_name='sharedwalletconfig')
    op.drop_table('sharedwalletconfig')

