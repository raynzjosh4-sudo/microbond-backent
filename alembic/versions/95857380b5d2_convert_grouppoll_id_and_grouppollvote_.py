"""convert grouppoll id and grouppollvote poll_id to uuid

Revision ID: 95857380b5d2
Revises: 4230cd2451ea
Create Date: 2026-10-11 18:03:06.893303

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '95857380b5d2'
down_revision: Union[str, Sequence[str], None] = '4230cd2451ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop foreign key and primary keys
    op.execute("ALTER TABLE IF EXISTS grouppollvote DROP CONSTRAINT IF EXISTS grouppollvote_poll_id_fkey;")
    op.execute("ALTER TABLE IF EXISTS grouppollvote DROP CONSTRAINT IF EXISTS grouppollvote_pkey;")
    op.execute("ALTER TABLE IF EXISTS grouppoll DROP CONSTRAINT IF EXISTS grouppoll_pkey;")

    # 2. Alter column types to UUID
    op.execute("ALTER TABLE grouppoll ALTER COLUMN id DROP DEFAULT;")
    op.execute("ALTER TABLE grouppoll ALTER COLUMN id TYPE UUID USING (gen_random_uuid());")
    op.execute("ALTER TABLE grouppoll ALTER COLUMN id SET DEFAULT gen_random_uuid();")

    op.execute("ALTER TABLE grouppollvote ALTER COLUMN poll_id TYPE UUID USING (gen_random_uuid());")

    # 3. Recreate primary keys and foreign key
    op.execute("ALTER TABLE grouppoll ADD PRIMARY KEY (id);")
    op.execute("ALTER TABLE grouppollvote ADD PRIMARY KEY (poll_id, user_id);")
    op.execute("ALTER TABLE grouppollvote ADD CONSTRAINT grouppollvote_poll_id_fkey FOREIGN KEY (poll_id) REFERENCES grouppoll(id) ON DELETE CASCADE;")


def downgrade() -> None:
    pass
