"""add_investment_club_and_association_dues_tables

Revision ID: 7418ca4e5877
Revises: 6307ba3d4766
Create Date: 2026-10-11 20:21:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '7418ca4e5877'
down_revision: Union[str, Sequence[str], None] = '6307ba3d4766'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create investment club and association dues tables."""

    # 1. investmentclubconfig
    op.create_table(
        'investmentclubconfig',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('group_id', sa.String(), nullable=False),
        sa.Column('share_unit_price', sa.BigInteger(), nullable=False),
        sa.Column('equity_calculation_mode', sa.String(), nullable=False, server_default='PROPORTIONAL_TO_SHARES'),
        sa.Column('voting_power_logic', sa.String(), nullable=False, server_default='PROPORTIONAL'),
        sa.Column('payout_destination_type', sa.String(), nullable=False, server_default='VERIFIED_BROKERS_ONLY'),
        sa.Column('dividend_distribution_rule', sa.String(), nullable=False, server_default='AUTO_PUSH_PROPORTIONAL'),
        sa.Column('lock_in_period_days', sa.Integer(), nullable=False, server_default='180'),
        sa.Column('liquidation_action', sa.String(), nullable=False, server_default='LIQUIDATE_PROPORTIONAL'),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['group.group_id'], name='investmentclubconfig_group_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='investmentclubconfig_pkey')
    )
    op.create_index('ix_investmentclubconfig_group_id', 'investmentclubconfig', ['group_id'], unique=True)

    # 2. investmentcluboperationalsettings
    op.create_table(
        'investmentcluboperationalsettings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('group_id', sa.String(), nullable=False),
        sa.Column('minimum_purchase_quota', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('proposal_approval_threshold_pct', sa.Integer(), nullable=False, server_default='66'),
        sa.Column('admin_management_fee_pct', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('allow_internal_share_transfers', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('enable_late_fees', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('current_balance', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_invested_capital', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_shares_issued', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_dividends_distributed', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['group.group_id'], name='investmentcluboperationalsettings_group_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='investmentcluboperationalsettings_pkey')
    )
    op.create_index('ix_investmentcluboperationalsettings_group_id', 'investmentcluboperationalsettings', ['group_id'], unique=True)

    # 3. investmentclubmembershare
    op.create_table(
        'investmentclubmembershare',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('group_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('shares_owned', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_invested', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('last_dividend_received', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['group.group_id'], name='investmentclubmembershare_group_id_fkey'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='investmentclubmembershare_user_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='investmentclubmembershare_pkey')
    )
    op.create_index('ix_investmentclubmembershare_group_id', 'investmentclubmembershare', ['group_id'])
    op.create_index('ix_investmentclubmembershare_user_id', 'investmentclubmembershare', ['user_id'])

    # 4. associationduesconfig
    op.create_table(
        'associationduesconfig',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('group_id', sa.String(), nullable=False),
        sa.Column('dues_amount', sa.BigInteger(), nullable=False),
        sa.Column('billing_cycle_days', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('billing_start_date', sa.BigInteger(), nullable=False),
        sa.Column('treasury_account_id', sa.String(), nullable=False),
        sa.Column('enable_prorated_dues', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['group.group_id'], name='associationduesconfig_group_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='associationduesconfig_pkey')
    )
    op.create_index('ix_associationduesconfig_group_id', 'associationduesconfig', ['group_id'], unique=True)

    # 5. associationduesoperationalsettings
    op.create_table(
        'associationduesoperationalsettings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('group_id', sa.String(), nullable=False),
        sa.Column('auto_sweep_trigger', sa.String(), nullable=False, server_default='END_OF_CYCLE'),
        sa.Column('allow_advance_payments', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('grace_period_days', sa.Integer(), nullable=False, server_default='7'),
        sa.Column('late_fee_amount', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('arrears_action', sa.String(), nullable=False, server_default='SUSPEND_MEMBERSHIP'),
        sa.Column('max_missed_cycles_allowed', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('show_defaulters_publicly', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('treasury_ledger_visibility', sa.String(), nullable=False, server_default='TRANSPARENT'),
        sa.Column('current_balance', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_collected', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_swept_to_treasury', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('active_defaulters_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['group.group_id'], name='associationduesoperationalsettings_group_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='associationduesoperationalsettings_pkey')
    )
    op.create_index('ix_associationduesoperationalsettings_group_id', 'associationduesoperationalsettings', ['group_id'], unique=True)

    # 6. associationmemberduesstanding
    op.create_table(
        'associationmemberduesstanding',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('group_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('cycles_paid_ahead', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('consecutive_missed_cycles', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('outstanding_arrears_balance', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('is_in_arrears', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_suspended', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('last_payment_date', sa.BigInteger(), nullable=True),
        sa.Column('next_due_date', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['group.group_id'], name='associationmemberduesstanding_group_id_fkey'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='associationmemberduesstanding_user_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='associationmemberduesstanding_pkey')
    )
    op.create_index('ix_associationmemberduesstanding_group_id', 'associationmemberduesstanding', ['group_id'])
    op.create_index('ix_associationmemberduesstanding_user_id', 'associationmemberduesstanding', ['user_id'])


def downgrade() -> None:
    """Drop investment club and association dues tables."""
    op.drop_table('associationmemberduesstanding')
    op.drop_table('associationduesoperationalsettings')
    op.drop_table('associationduesconfig')
    op.drop_table('investmentclubmembershare')
    op.drop_table('investmentcluboperationalsettings')
    op.drop_table('investmentclubconfig')
