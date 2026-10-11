"""Add missing user columns for security and referrals

Revision ID: e7f8a9b0c1d2
Revises: 9d47445a2816
Create Date: 2026-10-11 04:09:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, Sequence[str], None] = '9d47445a2816'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # Add missing security & fraud prevention columns to "user" table
    op.execute('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS primary_device_id VARCHAR;')
    op.execute('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS security_cooldown_until BIGINT;')
    op.execute('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS referral_code VARCHAR;')
    op.execute('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS referred_by_code VARCHAR;')
    op.execute('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS total_referrals INTEGER DEFAULT 0;')
    op.execute('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS total_earned DOUBLE PRECISION DEFAULT 0.0;')
    op.execute('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS guardian_id UUID;')
    op.execute('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS is_dependent_account BOOLEAN DEFAULT FALSE;')
    op.execute('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS daily_withdrawal_limit DOUBLE PRECISION DEFAULT 50000.0;')

def downgrade() -> None:
    op.drop_column('user', 'daily_withdrawal_limit')
    op.drop_column('user', 'is_dependent_account')
    op.drop_column('user', 'guardian_id')
    op.drop_column('user', 'total_earned')
    op.drop_column('user', 'total_referrals')
    op.drop_column('user', 'referred_by_code')
    op.drop_column('user', 'referral_code')
    op.drop_column('user', 'security_cooldown_until')
    op.drop_column('user', 'primary_device_id')
