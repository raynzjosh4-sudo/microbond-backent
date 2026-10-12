"""alter timestamp and balance columns to bigint

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-11 12:24:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Alter Group timestamp and balance columns to BIGINT to prevent 32-bit overflow with millisecond timestamps
    op.execute('ALTER TABLE "group" ALTER COLUMN "created_at" TYPE BIGINT;')
    op.execute('ALTER TABLE "group" ALTER COLUMN "updated_at" TYPE BIGINT;')
    op.execute('ALTER TABLE "group" ALTER COLUMN "total_balance" TYPE BIGINT;')

    # Alter GroupMembership timestamp columns to BIGINT
    op.execute('ALTER TABLE "groupmembership" ALTER COLUMN "joined_at" TYPE BIGINT;')
    op.execute('ALTER TABLE "groupmembership" ALTER COLUMN "left_at" TYPE BIGINT;')

    # Alter RotatingGroupDetails created_at to BIGINT
    op.execute('ALTER TABLE "rotatinggroupdetails" ALTER COLUMN "created_at" TYPE BIGINT;')

    # Alter TargetSavingsGroupDetails created_at to BIGINT
    op.execute('ALTER TABLE "targetsavingsgroupdetails" ALTER COLUMN "created_at" TYPE BIGINT;')

    # Alter UserPayoutDestination created_at to BIGINT
    op.execute('ALTER TABLE "userpayoutdestination" ALTER COLUMN "created_at" TYPE BIGINT;')

    # Alter UserPaymentMethod created_at to BIGINT
    op.execute('ALTER TABLE "userpaymentmethod" ALTER COLUMN "created_at" TYPE BIGINT;')

    # Group health metrics were moved to dedicated GroupHealth table; drop NOT NULL and set defaults on legacy columns
    op.execute("ALTER TABLE \"group\" ALTER COLUMN \"health_grade\" DROP NOT NULL;")
    op.execute("ALTER TABLE \"group\" ALTER COLUMN \"health_grade\" SET DEFAULT 'A+';")
    op.execute("ALTER TABLE \"group\" ALTER COLUMN \"on_time_repayment_rate_pct\" DROP NOT NULL;")
    op.execute("ALTER TABLE \"group\" ALTER COLUMN \"on_time_repayment_rate_pct\" SET DEFAULT 100.0;")
    op.execute("ALTER TABLE \"group\" ALTER COLUMN \"active_default_rate_pct\" DROP NOT NULL;")
    op.execute("ALTER TABLE \"group\" ALTER COLUMN \"active_default_rate_pct\" SET DEFAULT 0.0;")

    # Audit ledger delivery & compliance statements on groupcommunicationsettings
    op.execute('ALTER TABLE "groupcommunicationsettings" ADD COLUMN IF NOT EXISTS enable_automated_audit_dispatch BOOLEAN NOT NULL DEFAULT TRUE;')
    op.execute('ALTER TABLE "groupcommunicationsettings" ADD COLUMN IF NOT EXISTS audit_report_recipient_email VARCHAR;')
    op.execute('ALTER TABLE "groupcommunicationsettings" ADD COLUMN IF NOT EXISTS dispatch_monthly_compliance_statement BOOLEAN NOT NULL DEFAULT TRUE;')
    op.execute('ALTER TABLE "groupcommunicationsettings" ADD COLUMN IF NOT EXISTS export_file_format VARCHAR NOT NULL DEFAULT \'PDF\';')

    # Make collection_time optional on rotatinggroupdetails
    op.execute('ALTER TABLE "rotatinggroupdetails" ALTER COLUMN "collection_time" DROP NOT NULL;')


def downgrade() -> None:
    op.execute('ALTER TABLE "userpaymentmethod" ALTER COLUMN "created_at" TYPE INTEGER;')
    op.execute('ALTER TABLE "userpayoutdestination" ALTER COLUMN "created_at" TYPE INTEGER;')
    op.execute('ALTER TABLE "targetsavingsgroupdetails" ALTER COLUMN "created_at" TYPE INTEGER;')
    op.execute('ALTER TABLE "rotatinggroupdetails" ALTER COLUMN "created_at" TYPE INTEGER;')
    op.execute('ALTER TABLE "groupmembership" ALTER COLUMN "left_at" TYPE INTEGER;')
    op.execute('ALTER TABLE "groupmembership" ALTER COLUMN "joined_at" TYPE INTEGER;')
    op.execute('ALTER TABLE "group" ALTER COLUMN "total_balance" TYPE INTEGER;')
    op.execute('ALTER TABLE "group" ALTER COLUMN "updated_at" TYPE INTEGER;')
    op.execute('ALTER TABLE "group" ALTER COLUMN "created_at" TYPE INTEGER;')
