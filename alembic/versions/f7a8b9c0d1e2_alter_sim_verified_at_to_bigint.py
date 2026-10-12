"""alter sim_verified_at and kycdocument timestamp columns to bigint

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-10-11 14:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, None] = 'e6f7a8b9c0d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('ALTER TABLE "kycprofile" ALTER COLUMN "sim_verified_at" TYPE BIGINT;')
    op.execute('ALTER TABLE "kycdocument" ALTER COLUMN "submitted_at" TYPE BIGINT;')
    op.execute('ALTER TABLE "kycdocument" ALTER COLUMN "verified_at" TYPE BIGINT;')
    op.execute('ALTER TABLE "kycdocument" ALTER COLUMN "expiry_date" TYPE BIGINT;')
    op.execute('ALTER TABLE "user" ALTER COLUMN "last_seen_at" TYPE BIGINT;')


def downgrade() -> None:
    op.execute('ALTER TABLE "kycprofile" ALTER COLUMN "sim_verified_at" TYPE INTEGER;')
    op.execute('ALTER TABLE "kycdocument" ALTER COLUMN "submitted_at" TYPE INTEGER;')
    op.execute('ALTER TABLE "kycdocument" ALTER COLUMN "verified_at" TYPE INTEGER;')
    op.execute('ALTER TABLE "kycdocument" ALTER COLUMN "expiry_date" TYPE INTEGER;')
    op.execute('ALTER TABLE "user" ALTER COLUMN "last_seen_at" TYPE INTEGER;')
