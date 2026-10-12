"""add_fundraiser_campaign_config_and_live_stats_tables

Revision ID: 90bf9550c526
Revises: 70f802cd6a0e
Create Date: 2026-10-11 19:23:25.738757

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = '90bf9550c526'
down_revision = '70f802cd6a0e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create fundraisercampaignconfig and fundraiserlivestats tables."""

    op.create_table(
        'fundraisercampaignconfig',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('group_id', sqlmodel.AutoString(), nullable=False),
        sa.Column('target_amount', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('campaign_deadline', sa.BigInteger(), nullable=True),
        sa.Column('payout_destination_type', sqlmodel.AutoString(), nullable=False, server_default='NOMINATED_ACCOUNT'),
        sa.Column('nominated_account_id', sqlmodel.AutoString(), nullable=True),
        sa.Column('payout_trigger_mode', sqlmodel.AutoString(), nullable=False, server_default='MANUAL'),
        sa.Column('require_multi_signoff', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('signoff_count_required', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['group.group_id'], name='fundraisercampaignconfig_group_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='fundraisercampaignconfig_pkey'),
    )
    op.create_index('ix_fundraisercampaignconfig_group_id', 'fundraisercampaignconfig', ['group_id'], unique=True)

    op.create_table(
        'fundraiserlivestats',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('group_id', sqlmodel.AutoString(), nullable=False),
        sa.Column('allow_overfunding', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('stop_on_target_reached', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('minimum_donation_amount', sa.BigInteger(), nullable=False, server_default='500'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_paid_out', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('total_raised', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('donor_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['group.group_id'], name='fundraiserlivestats_group_id_fkey'),
        sa.PrimaryKeyConstraint('id', name='fundraiserlivestats_pkey'),
    )
    op.create_index('ix_fundraiserlivestats_group_id', 'fundraiserlivestats', ['group_id'], unique=True)


def downgrade() -> None:
    """Drop fundraiser tables."""
    op.drop_index('ix_fundraiserlivestats_group_id', table_name='fundraiserlivestats')
    op.drop_table('fundraiserlivestats')
    op.drop_index('ix_fundraisercampaignconfig_group_id', table_name='fundraisercampaignconfig')
    op.drop_table('fundraisercampaignconfig')
