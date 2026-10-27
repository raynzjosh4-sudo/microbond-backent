"""add minimum_partial_payment_amount to rotatinggroupdetails

Revision ID: 9f8e7d6c5b4a
Revises: f1a2b3c4d5e6
Create Date: 2026-10-27 22:15:00.000000

Allows the group admin to set the minimum amount a member must pay per deposit
when partial payments are enabled.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '9f8e7d6c5b4a'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    is_postgres = conn.dialect.name == "postgresql"

    if is_postgres:
        conn.execute(sa.text('ALTER TABLE "rotatinggroupdetails" ADD COLUMN IF NOT EXISTS "minimum_partial_payment_amount" DOUBLE PRECISION NULL;'))
    else:
        try:
            op.add_column(
                'rotatinggroupdetails',
                sa.Column('minimum_partial_payment_amount', sa.Float(), nullable=True)
            )
        except Exception:
            pass


def downgrade() -> None:
    op.drop_column('rotatinggroupdetails', 'minimum_partial_payment_amount')
