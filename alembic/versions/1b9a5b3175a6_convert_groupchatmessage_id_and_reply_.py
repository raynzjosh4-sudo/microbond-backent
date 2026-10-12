"""convert groupchatmessage id and reply_to to uuid

Revision ID: 1b9a5b3175a6
Revises: f7a8b9c0d1e2
Create Date: 2026-10-11 17:09:15.435826

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '1b9a5b3175a6'
down_revision: Union[str, Sequence[str], None] = 'f7a8b9c0d1e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop existing foreign keys
    op.execute("ALTER TABLE IF EXISTS groupchatreadreceipt DROP CONSTRAINT IF EXISTS groupchatreadreceipt_message_id_fkey;")
    op.execute("ALTER TABLE IF EXISTS groupchatmessage DROP CONSTRAINT IF EXISTS groupchatmessage_reply_to_message_id_fkey;")
    op.execute("ALTER TABLE IF EXISTS groupchatreadreceipt DROP CONSTRAINT IF EXISTS groupchatreadreceipt_pkey;")
    op.execute("ALTER TABLE IF EXISTS groupchatmessage DROP CONSTRAINT IF EXISTS groupchatmessage_pkey;")

    # 2. Alter column types to UUID
    op.execute("ALTER TABLE groupchatmessage ALTER COLUMN id DROP DEFAULT;")
    op.execute("ALTER TABLE groupchatmessage ALTER COLUMN id TYPE UUID USING (gen_random_uuid());")
    op.execute("ALTER TABLE groupchatmessage ALTER COLUMN id SET DEFAULT gen_random_uuid();")

    op.execute("ALTER TABLE groupchatmessage ALTER COLUMN reply_to_message_id TYPE UUID USING NULL;")

    op.execute("ALTER TABLE groupchatreadreceipt ALTER COLUMN message_id TYPE UUID USING (gen_random_uuid());")

    # 3. Re-add primary keys and foreign keys
    op.execute("ALTER TABLE groupchatmessage ADD PRIMARY KEY (id);")
    op.execute("ALTER TABLE groupchatreadreceipt ADD PRIMARY KEY (message_id, user_id);")
    op.execute("ALTER TABLE groupchatmessage ADD CONSTRAINT groupchatmessage_reply_to_message_id_fkey FOREIGN KEY (reply_to_message_id) REFERENCES groupchatmessage(id) ON DELETE SET NULL;")
    op.execute("ALTER TABLE groupchatreadreceipt ADD CONSTRAINT groupchatreadreceipt_message_id_fkey FOREIGN KEY (message_id) REFERENCES groupchatmessage(id) ON DELETE CASCADE;")


def downgrade() -> None:
    pass
