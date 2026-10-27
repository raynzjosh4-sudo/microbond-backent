"""Add saving_days_per_cycle and current_saving_day to rotatinggroupdetails

Revision ID: f1a2b3c4d5e6
Revises: e1f2a3b4c5d6
Create Date: 2026-10-27 21:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    is_postgres = conn.dialect.name == "postgresql"

    if is_postgres:
        # Make contribution_amount nullable to support draft circles
        conn.execute(sa.text('ALTER TABLE "rotatinggroupdetails" ALTER COLUMN "contribution_amount" DROP NOT NULL;'))
        
        # Add missing saving days and current day columns
        conn.execute(sa.text('ALTER TABLE "rotatinggroupdetails" ADD COLUMN IF NOT EXISTS "saving_days_per_cycle" INTEGER NULL;'))
        conn.execute(sa.text('ALTER TABLE "rotatinggroupdetails" ADD COLUMN IF NOT EXISTS "current_saving_day" INTEGER NOT NULL DEFAULT 0;'))
    else:
        # SQLite / Generic dialect fallback
        cols = [
            ("saving_days_per_cycle", sa.Column("saving_days_per_cycle", sa.Integer(), nullable=True)),
            ("current_saving_day", sa.Column("current_saving_day", sa.Integer(), nullable=False, server_default="0"))
        ]
        for col_name, col_def in cols:
            try:
                op.add_column("rotatinggroupdetails", col_def)
            except Exception:
                pass


def downgrade() -> None:
    conn = op.get_bind()
    is_postgres = conn.dialect.name == "postgresql"
    if is_postgres:
        conn.execute(sa.text('ALTER TABLE "rotatinggroupdetails" DROP COLUMN IF EXISTS "saving_days_per_cycle";'))
        conn.execute(sa.text('ALTER TABLE "rotatinggroupdetails" DROP COLUMN IF EXISTS "current_saving_day";'))
    else:
        try:
            op.drop_column("rotatinggroupdetails", "saving_days_per_cycle")
            op.drop_column("rotatinggroupdetails", "current_saving_day")
        except Exception:
            pass
