"""update targetsavingsgroupdetails schema for goal savings

Revision ID: 70f802cd6a0e
Revises: 95857380b5d2
Create Date: 2026-10-11 18:33:58.117028

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '70f802cd6a0e'
down_revision: Union[str, Sequence[str], None] = '95857380b5d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop existing table and recreate with UUID primary key and strict integer currencies
    op.execute("DROP TABLE IF EXISTS targetsavingsgroupdetails CASCADE;")
    
    op.execute("""
        CREATE TABLE targetsavingsgroupdetails (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            group_id VARCHAR NOT NULL UNIQUE REFERENCES "group"(group_id) ON DELETE CASCADE,
            
            -- Savings Goal & Schedule (Whole Numbers Only)
            target_amount BIGINT NOT NULL DEFAULT 0,
            target_date BIGINT NOT NULL,
            contribution_amount BIGINT NOT NULL DEFAULT 0,
            collection_frequency_days INTEGER NOT NULL DEFAULT 0,
            collection_time BIGINT,
            
            -- Where the Money Goes at the End
            payout_destination_type VARCHAR NOT NULL DEFAULT 'PROPORTIONAL_RETURN',
            nominated_account_id VARCHAR,
            
            -- Group Agreement & Voting Rules
            require_consensus_at_end BOOLEAN NOT NULL DEFAULT FALSE,
            allow_early_payout_by_vote BOOLEAN NOT NULL DEFAULT TRUE,
            vote_approval_percentage INTEGER NOT NULL DEFAULT 100,
            
            -- Late Fees & Rules
            enable_late_fees BOOLEAN NOT NULL DEFAULT FALSE,
            late_fee_amount BIGINT NOT NULL DEFAULT 0,
            grace_period_hours INTEGER NOT NULL DEFAULT 24,
            missed_payment_action VARCHAR NOT NULL DEFAULT 'RECORD_STRIKE',
            minimum_kyc_tier INTEGER NOT NULL DEFAULT 1,
            hide_leaderboard BOOLEAN NOT NULL DEFAULT FALSE,
            
            -- Savings Status
            is_locked BOOLEAN NOT NULL DEFAULT TRUE,
            is_ended BOOLEAN NOT NULL DEFAULT FALSE,
            is_paid_out BOOLEAN NOT NULL DEFAULT FALSE,
            total_saved_amount BIGINT NOT NULL DEFAULT 0,
            created_at BIGINT NOT NULL
        );
        CREATE INDEX ix_targetsavingsgroupdetails_group_id ON targetsavingsgroupdetails(group_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS targetsavingsgroupdetails CASCADE;")
