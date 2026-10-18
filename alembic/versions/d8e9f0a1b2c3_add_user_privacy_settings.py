"""Add user personal privacy settings columns

Revision ID: d8e9f0a1b2c3
Revises: c7d8e9f0a1b2
Create Date: 2026-10-18 08:20:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8e9f0a1b2c3'
down_revision: Union[str, Sequence[str], None] = 'c7d8e9f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add personal privacy settings to "user" table
    op.execute('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS profile_photo_visibility VARCHAR DEFAULT \'EVERYONE\';')
    op.execute('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS about_visibility VARCHAR DEFAULT \'EVERYONE\';')
    op.execute('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS group_add_permission VARCHAR DEFAULT \'EVERYONE\';')

    # Also handle alternate "users" table name if present in any environment
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = 'users') THEN
                EXECUTE 'ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_photo_visibility VARCHAR DEFAULT ''EVERYONE'';';
                EXECUTE 'ALTER TABLE users ADD COLUMN IF NOT EXISTS about_visibility VARCHAR DEFAULT ''EVERYONE'';';
                EXECUTE 'ALTER TABLE users ADD COLUMN IF NOT EXISTS group_add_permission VARCHAR DEFAULT ''EVERYONE'';';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute('ALTER TABLE "user" DROP COLUMN IF EXISTS group_add_permission;')
    op.execute('ALTER TABLE "user" DROP COLUMN IF EXISTS about_visibility;')
    op.execute('ALTER TABLE "user" DROP COLUMN IF EXISTS profile_photo_visibility;')
