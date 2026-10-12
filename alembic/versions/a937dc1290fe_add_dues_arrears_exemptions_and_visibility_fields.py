"""add_dues_arrears_exemptions_and_visibility_fields

Revision ID: a937dc1290fe
Revises: 8529cb5f1234
Create Date: 2026-10-12 02:35:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a937dc1290fe'
down_revision: Union[str, Sequence[str], None] = '8529cb5f1234'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add columns to associationduesoperationalsettings
    op.add_column('associationduesoperationalsettings', sa.Column('allow_installments', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('associationduesoperationalsettings', sa.Column('send_arrears_reminders', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('associationduesoperationalsettings', sa.Column('arrears_reminder_days_before', sa.Integer(), nullable=False, server_default='3'))
    op.add_column('associationduesoperationalsettings', sa.Column('restrict_voting_on_arrears', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('associationduesoperationalsettings', sa.Column('restrict_welfare_claims_on_arrears', sa.Boolean(), nullable=False, server_default='true'))

    # 2. Create associationduesexemption table
    op.create_table(
        'associationduesexemption',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('group_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('exemption_type', sa.String(), nullable=False, server_default='TEMPORARY'),
        sa.Column('reason', sa.String(), nullable=False, server_default='HARDSHIP'),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('discount_percentage', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('start_date', sa.BigInteger(), nullable=False),
        sa.Column('end_date', sa.BigInteger(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('approved_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['group.group_id'], name='associationduesexemption_group_id_fkey'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], name='associationduesexemption_user_id_fkey'),
        sa.ForeignKeyConstraint(['approved_by'], ['user.id'], name='associationduesexemption_approved_by_fkey'),
        sa.PrimaryKeyConstraint('id', name='associationduesexemption_pkey')
    )
    op.create_index('ix_associationduesexemption_group_id', 'associationduesexemption', ['group_id'], unique=False)
    op.create_index('ix_associationduesexemption_user_id', 'associationduesexemption', ['user_id'], unique=False)

    # 3. Add dues-specific visibility toggles to groupvisibilitysettings
    op.add_column('groupvisibilitysettings', sa.Column('vis_dues_schedule', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('groupvisibilitysettings', sa.Column('vis_allow_installments', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('groupvisibilitysettings', sa.Column('vis_arrears_policy', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('groupvisibilitysettings', sa.Column('vis_fee_exemptions', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('groupvisibilitysettings', sa.Column('vis_pending_dues_adjustments', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('groupvisibilitysettings', sa.Column('vis_broadcast_individual_dues_receipts', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('groupvisibilitysettings', sa.Column('vis_announce_dues_adjustment_updates', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('groupvisibilitysettings', sa.Column('vis_send_dues_due_prompts', sa.Boolean(), nullable=False, server_default='true'))

    # 4. Add communication fields to groupcommunicationsettings
    op.add_column('groupcommunicationsettings', sa.Column('send_dues_due_prompts', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('groupcommunicationsettings', sa.Column('broadcast_individual_dues_receipts', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('groupcommunicationsettings', sa.Column('announce_dues_adjustment_updates', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    # 4. Drop communication fields
    op.drop_column('groupcommunicationsettings', 'announce_dues_adjustment_updates')
    op.drop_column('groupcommunicationsettings', 'broadcast_individual_dues_receipts')
    op.drop_column('groupcommunicationsettings', 'send_dues_due_prompts')

    # 3. Drop visibility toggles
    op.drop_column('groupvisibilitysettings', 'vis_send_dues_due_prompts')
    op.drop_column('groupvisibilitysettings', 'vis_announce_dues_adjustment_updates')
    op.drop_column('groupvisibilitysettings', 'vis_broadcast_individual_dues_receipts')
    op.drop_column('groupvisibilitysettings', 'vis_pending_dues_adjustments')
    op.drop_column('groupvisibilitysettings', 'vis_fee_exemptions')
    op.drop_column('groupvisibilitysettings', 'vis_arrears_policy')
    op.drop_column('groupvisibilitysettings', 'vis_allow_installments')
    op.drop_column('groupvisibilitysettings', 'vis_dues_schedule')

    # 2. Drop exemption table
    op.drop_index('ix_associationduesexemption_user_id', table_name='associationduesexemption')
    op.drop_index('ix_associationduesexemption_group_id', table_name='associationduesexemption')
    op.drop_table('associationduesexemption')

    # 1. Drop operational settings columns
    op.drop_column('associationduesoperationalsettings', 'restrict_welfare_claims_on_arrears')
    op.drop_column('associationduesoperationalsettings', 'restrict_voting_on_arrears')
    op.drop_column('associationduesoperationalsettings', 'arrears_reminder_days_before')
    op.drop_column('associationduesoperationalsettings', 'send_arrears_reminders')
    op.drop_column('associationduesoperationalsettings', 'allow_installments')
