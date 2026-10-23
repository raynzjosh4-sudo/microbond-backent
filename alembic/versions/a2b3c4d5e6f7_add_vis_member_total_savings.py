"""Add vis_member_total_savings to groupvisibilitysettings

Revision ID: a2b3c4d5e6f7
Revises: d8e9f0a1b2c3
Create Date: 2026-10-23 20:38:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = 'd8e9f0a1b2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add vis_member_total_savings column — idempotent, skips if already exists."""
    conn = op.get_bind()
    # Check if column already exists before adding (safe for re-runs on cold starts)
    result = conn.execute(sa.text("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'groupvisibilitysettings'
        AND column_name = 'vis_member_total_savings'
    """))
    if result.fetchone() is None:
        op.add_column(
            'groupvisibilitysettings',
            sa.Column('vis_member_total_savings', sa.Boolean(), nullable=False, server_default=sa.true())
        )


def downgrade() -> None:
    """Remove vis_member_total_savings column."""
    op.drop_column('groupvisibilitysettings', 'vis_member_total_savings')
