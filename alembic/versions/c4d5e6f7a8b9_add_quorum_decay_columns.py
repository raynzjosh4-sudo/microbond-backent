"""add quorum decay columns to groupgovernancesettings

Revision ID: c4d5e6f7a8b9
Revises: b2c3d4e5f6a7
Create Date: 2026-10-11 13:22:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add missing quorum decay columns to groupgovernancesettings
    op.add_column('groupgovernancesettings',
        sa.Column('enable_quorum_decay', sa.Boolean(), nullable=False, server_default='true')
    )
    op.add_column('groupgovernancesettings',
        sa.Column('quorum_decay_hours', sa.Integer(), nullable=False, server_default='48')
    )
    op.add_column('groupgovernancesettings',
        sa.Column('quorum_decay_minimum_approvals', sa.Integer(), nullable=False, server_default='2')
    )


def downgrade() -> None:
    op.drop_column('groupgovernancesettings', 'quorum_decay_minimum_approvals')
    op.drop_column('groupgovernancesettings', 'quorum_decay_hours')
    op.drop_column('groupgovernancesettings', 'enable_quorum_decay')
