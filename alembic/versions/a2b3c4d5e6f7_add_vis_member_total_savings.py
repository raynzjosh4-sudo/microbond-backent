"""Add vis_member_total_savings to groupvisibilitysettings

Revision ID: a2b3c4d5e6f7
Revises: 9d47445a2816
Create Date: 2026-10-23 20:38:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = 'd8e9f0a1b2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add vis_member_total_savings column (defaults to True = members can see their savings)."""
    op.add_column(
        'groupvisibilitysettings',
        sa.Column('vis_member_total_savings', sa.Boolean(), nullable=False, server_default=sa.text('1'))
    )


def downgrade() -> None:
    """Remove vis_member_total_savings column."""
    op.drop_column('groupvisibilitysettings', 'vis_member_total_savings')
