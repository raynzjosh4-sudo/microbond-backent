"""add verification fields to payout destination and payment method

Revision ID: a1b2c3d4e5f6
Revises: e7f8a9b0c1d2
Create Date: 2026-10-11 10:05:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add verification fields to userpayoutdestination
    op.execute('ALTER TABLE "userpayoutdestination" ADD COLUMN IF NOT EXISTS account_type VARCHAR DEFAULT \'MOBILE_MONEY\';')
    op.execute('ALTER TABLE "userpayoutdestination" ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;')
    op.execute('ALTER TABLE "userpayoutdestination" ADD COLUMN IF NOT EXISTS verified_name VARCHAR;')
    op.execute('ALTER TABLE "userpayoutdestination" ADD COLUMN IF NOT EXISTS verification_type VARCHAR;')
    op.execute('ALTER TABLE "userpayoutdestination" ALTER COLUMN "account_name" DROP NOT NULL;')

    # Add verification fields to userpaymentmethod
    op.execute('ALTER TABLE "userpaymentmethod" ADD COLUMN IF NOT EXISTS account_type VARCHAR DEFAULT \'MOBILE_MONEY\';')
    op.execute('ALTER TABLE "userpaymentmethod" ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;')
    op.execute('ALTER TABLE "userpaymentmethod" ADD COLUMN IF NOT EXISTS verified_name VARCHAR;')
    op.execute('ALTER TABLE "userpaymentmethod" ADD COLUMN IF NOT EXISTS verification_type VARCHAR;')
    op.execute('ALTER TABLE "userpaymentmethod" ALTER COLUMN "account_name" DROP NOT NULL;')


def downgrade() -> None:
    op.drop_column('userpaymentmethod', 'verification_type')
    op.drop_column('userpaymentmethod', 'verified_name')
    op.drop_column('userpaymentmethod', 'is_verified')
    op.drop_column('userpaymentmethod', 'account_type')

    op.drop_column('userpayoutdestination', 'verification_type')
    op.drop_column('userpayoutdestination', 'verified_name')
    op.drop_column('userpayoutdestination', 'is_verified')
    op.drop_column('userpayoutdestination', 'account_type')
