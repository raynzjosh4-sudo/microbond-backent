"""add_bill_split_tables

Revision ID: 8529cb5f1234
Revises: 7418ca4e5877
Create Date: 2026-10-11 20:52:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '8529cb5f1234'
down_revision: Union[str, Sequence[str], None] = '7418ca4e5877'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create bill split tables."""

    # 1. billsplitconfig
    op.create_table(
        'billsplitconfig',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('group_id', sa.String(), nullable=False),
        sa.Column('total_bill_amount', sa.BigInteger(), nullable=False),
        sa.Column('split_mode', sa.String(), nullable=False, server_default='EQUAL'),
        sa.Column('settlement_deadline', sa.BigInteger(), nullable=True),
        sa.Column('bill_category', sa.String(), nullable=False, server_default='GENERAL'),
        sa.Column('payout_destination_type', sa.String(), nullable=False, server_default='ORGANIZER_WALLET'),
        sa.Column('payee_identifier', sa.String(), nullable=True),
        sa.Column('payee_name', sa.String(), nullable=True),
        sa.Column('bill_receipt_url', sa.String(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['group.group_id'], name='billsplitconfig_group_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='billsplitconfig_pkey')
    )
    op.create_index('ix_billsplitconfig_group_id', 'billsplitconfig', ['group_id'], unique=True)

    # 2. billsplitoperationalsettings
    op.create_table(
        'billsplitoperationalsettings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('group_id', sa.String(), nullable=False),
        sa.Column('allow_tip_or_extra', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('auto_close_on_settlement', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('send_reminder_hours_before', sa.Integer(), nullable=False, server_default='24'),
        sa.Column('enable_late_fees', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('late_fee_amount', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('grace_period_hours', sa.Integer(), nullable=False, server_default='24'),
        sa.Column('is_settled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('total_collected', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('total_tip_collected', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('settled_at', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['group.group_id'], name='billsplitoperationalsettings_group_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='billsplitoperationalsettings_pkey')
    )
    op.create_index('ix_billsplitoperationalsettings_group_id', 'billsplitoperationalsettings', ['group_id'], unique=True)

    # 3. billsplitmembershare
    op.create_table(
        'billsplitmembershare',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('group_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('assigned_amount', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('amount_paid', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('tip_paid', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('is_settled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('paid_at', sa.BigInteger(), nullable=True),
        sa.Column('payment_reference', sa.String(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['group.group_id'], name='billsplitmembershare_group_id_fkey'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='billsplitmembershare_user_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='billsplitmembershare_pkey')
    )
    op.create_index('ix_billsplitmembershare_group_id', 'billsplitmembershare', ['group_id'], unique=False)
    op.create_index('ix_billsplitmembershare_user_id', 'billsplitmembershare', ['user_id'], unique=False)


def downgrade() -> None:
    """Drop bill split tables."""
    op.drop_index('ix_billsplitmembershare_user_id', table_name='billsplitmembershare')
    op.drop_index('ix_billsplitmembershare_group_id', table_name='billsplitmembershare')
    op.drop_table('billsplitmembershare')

    op.drop_index('ix_billsplitoperationalsettings_group_id', table_name='billsplitoperationalsettings')
    op.drop_table('billsplitoperationalsettings')

    op.drop_index('ix_billsplitconfig_group_id', table_name='billsplitconfig')
    op.drop_table('billsplitconfig')
