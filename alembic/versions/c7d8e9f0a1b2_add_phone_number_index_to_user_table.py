"""Add index on user phone_number for rapid contact discovery

Revision ID: c7d8e9f0a1b2
Revises: b1c2d3e4f5a6
Create Date: 2026-10-15 07:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, Sequence[str], None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Optimized B-Tree index on phone_number for sub-millisecond address book batch lookups.
    # Checks both Postgres standard "user" table (SQLModel default) and "users" if present.
    op.execute('CREATE INDEX IF NOT EXISTS idx_users_phone_number ON "user" (phone_number);')
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'users') THEN
                EXECUTE 'CREATE INDEX IF NOT EXISTS idx_users_phone_number_alt ON users (phone_number);';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute('DROP INDEX IF EXISTS idx_users_phone_number;')
    op.execute('DROP INDEX IF EXISTS idx_users_phone_number_alt;')
