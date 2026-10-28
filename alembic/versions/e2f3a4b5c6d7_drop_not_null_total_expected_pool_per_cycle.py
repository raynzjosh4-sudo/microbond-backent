"""drop not null constraint from total_expected_pool_per_cycle in rotatinggroupdetails

Revision ID: e2f3a4b5c6d7
Revises: 9f8e7d6c5b4a
Create Date: 2026-10-28 09:35:00.000000

Allows draft and unfinalized rotating groups to be created with total_expected_pool_per_cycle as NULL.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, Sequence[str], None] = '9f8e7d6c5b4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    is_postgres = conn.dialect.name == "postgresql"

    if is_postgres:
        conn.execute(sa.text('ALTER TABLE "rotatinggroupdetails" ALTER COLUMN "total_expected_pool_per_cycle" DROP NOT NULL;'))
    else:
        # SQLite / Generic dialect does not enforce NOT NULL altering without table rewrite
        pass


def downgrade() -> None:
    pass

