"""add minimum_partial_payment_amount to rotatinggroupdetails

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-10-27

Allows the group admin to set the minimum amount a member must pay per deposit
when partial payments are enabled, instead of using the hardcoded backend default.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'rotatinggroupdetails',
        sa.Column(
            'minimum_partial_payment_amount',
            sa.Float(),
            nullable=True,
            comment='Admin-set minimum amount per partial deposit. NULL = fallback to 1,000 UGX default.'
        )
    )


def downgrade() -> None:
    op.drop_column('rotatinggroupdetails', 'minimum_partial_payment_amount')
