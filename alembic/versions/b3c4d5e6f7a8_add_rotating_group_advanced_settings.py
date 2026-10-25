"""Add rotating group advanced settings

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-10-25 03:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Columns to add to rotatinggroupdetails: (column_name, sa_column)
    rotating_cols = [
        ('auto_disburse_when_full', sa.Column('auto_disburse_when_full', sa.Boolean(), nullable=False, server_default=sa.true())),
        ('multi_sig_payout_approval', sa.Column('multi_sig_payout_approval', sa.Boolean(), nullable=False, server_default=sa.false())),
        ('allow_turn_swaps', sa.Column('allow_turn_swaps', sa.Boolean(), nullable=False, server_default=sa.true())),
        ('turn_swap_approval_mode', sa.Column('turn_swap_approval_mode', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='MUTUAL_CONSENT')),
        ('early_turn_security_hold_percentage', sa.Column('early_turn_security_hold_percentage', sa.Float(), nullable=False, server_default='0.0')),
        ('require_guarantors_for_early_turns_only', sa.Column('require_guarantors_for_early_turns_only', sa.Boolean(), nullable=False, server_default=sa.true())),
        ('auto_renew_cycle', sa.Column('auto_renew_cycle', sa.Boolean(), nullable=False, server_default=sa.false())),
        ('reverse_payout_order_on_renew', sa.Column('reverse_payout_order_on_renew', sa.Boolean(), nullable=False, server_default=sa.true())),
        ('reminder_lead_time_hours', sa.Column('reminder_lead_time_hours', sa.Integer(), nullable=False, server_default='24')),
        ('enable_auto_debit_prompt', sa.Column('enable_auto_debit_prompt', sa.Boolean(), nullable=False, server_default=sa.true())),
    ]

    for col_name, col_def in rotating_cols:
        res = conn.execute(sa.text(f"""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'rotatinggroupdetails'
            AND column_name = '{col_name}'
        """))
        if res.fetchone() is None:
            op.add_column('rotatinggroupdetails', col_def)

    # Columns to add to groupgovernancesettings
    gov_res = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'groupgovernancesettings'
        AND column_name = 'turn_swap_approval_mode'
    """))
    if gov_res.fetchone() is None:
        op.add_column(
            'groupgovernancesettings',
            sa.Column('turn_swap_approval_mode', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='MUTUAL_CONSENT')
        )


def downgrade() -> None:
    conn = op.get_bind()

    # Columns to drop from rotatinggroupdetails
    rotating_cols = [
        'auto_disburse_when_full',
        'multi_sig_payout_approval',
        'allow_turn_swaps',
        'turn_swap_approval_mode',
        'early_turn_security_hold_percentage',
        'require_guarantors_for_early_turns_only',
        'auto_renew_cycle',
        'reverse_payout_order_on_renew',
        'reminder_lead_time_hours',
        'enable_auto_debit_prompt',
    ]

    for col_name in rotating_cols:
        res = conn.execute(sa.text(f"""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'rotatinggroupdetails'
            AND column_name = '{col_name}'
        """))
        if res.fetchone() is not None:
            op.drop_column('rotatinggroupdetails', col_name)

    gov_res = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'groupgovernancesettings'
        AND column_name = 'turn_swap_approval_mode'
    """))
    if gov_res.fetchone() is not None:
        op.drop_column('groupgovernancesettings', 'turn_swap_approval_mode')
