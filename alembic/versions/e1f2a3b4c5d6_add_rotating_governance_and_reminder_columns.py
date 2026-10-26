"""Add rotating governance, prepaid surplus, reports, and reminder tier columns

Revision ID: e1f2a3b4c5d6
Revises: c5d6e7f8a9b0
Create Date: 2026-10-26 23:45:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'c5d6e7f8a9b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    is_postgres = conn.dialect.name == "postgresql"

    # Helper function to add column if not exists
    def safe_add_column(table: str, col_name: str, col_type_sql: str):
        if is_postgres:
            conn.execute(sa.text(f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS "{col_name}" {col_type_sql};'))
        else:
            try:
                conn.execute(sa.text(f'ALTER TABLE "{table}" ADD COLUMN "{col_name}" {col_type_sql};'))
            except Exception:
                pass

    # 1. Member Obligation: last_reminder_tier
    safe_add_column("memberobligation", "last_reminder_tier", "INTEGER")

    # 2. Group Membership: credit_balance_ugx
    safe_add_column("groupmembership", "credit_balance_ugx", "BIGINT NOT NULL DEFAULT 0")

    # 3. Group Wallet: prepaid_funds
    safe_add_column("groupwallet", "prepaid_funds", "BIGINT NOT NULL DEFAULT 0")

    # 4. Group Financial Settings: enforce_payout_holds
    safe_add_column("groupfinancialsettings", "enforce_payout_holds", "BOOLEAN NOT NULL DEFAULT FALSE")

    # 5. Group Report: reported_user_id
    safe_add_column("groupreport", "reported_user_id", "UUID" if is_postgres else "VARCHAR")

    # 6. Rotating Group Details advanced fields
    safe_add_column("rotatinggroupdetails", "auto_disburse_when_full", "BOOLEAN NOT NULL DEFAULT TRUE")
    safe_add_column("rotatinggroupdetails", "multi_sig_payout_approval", "BOOLEAN NOT NULL DEFAULT FALSE")
    safe_add_column("rotatinggroupdetails", "allow_turn_swaps", "BOOLEAN NOT NULL DEFAULT TRUE")
    safe_add_column("rotatinggroupdetails", "turn_swap_approval_mode", "VARCHAR NOT NULL DEFAULT 'MUTUAL_CONSENT'")
    safe_add_column("rotatinggroupdetails", "early_turn_security_hold_percentage", "DOUBLE PRECISION NOT NULL DEFAULT 0.0" if is_postgres else "FLOAT NOT NULL DEFAULT 0.0")
    safe_add_column("rotatinggroupdetails", "require_guarantors_for_early_turns_only", "BOOLEAN NOT NULL DEFAULT TRUE")
    safe_add_column("rotatinggroupdetails", "auto_renew_cycle", "BOOLEAN NOT NULL DEFAULT FALSE")
    safe_add_column("rotatinggroupdetails", "reverse_payout_order_on_renew", "BOOLEAN NOT NULL DEFAULT TRUE")
    safe_add_column("rotatinggroupdetails", "reminder_lead_time_hours", "INTEGER NOT NULL DEFAULT 24")
    safe_add_column("rotatinggroupdetails", "enable_auto_debit_prompt", "BOOLEAN NOT NULL DEFAULT TRUE")
    safe_add_column("rotatinggroupdetails", "current_cycle", "INTEGER NOT NULL DEFAULT 1")

    # 7. Rotating Cycle Report Table
    if is_postgres:
        conn.execute(sa.text('''
            CREATE TABLE IF NOT EXISTS "rotatingcyclereport" (
                id SERIAL PRIMARY KEY,
                report_id VARCHAR UNIQUE,
                group_id VARCHAR,
                cycle_number INTEGER,
                report_type VARCHAR DEFAULT 'ROTATING_CYCLE_COMPLETION',
                expected_pool_target BIGINT DEFAULT 0,
                actual_collected_amount BIGINT DEFAULT 0,
                collection_rate_percentage DOUBLE PRECISION DEFAULT 0.0,
                gross_payout_amount BIGINT DEFAULT 0,
                early_security_hold_deducted BIGINT DEFAULT 0,
                net_payout_disbursed BIGINT DEFAULT 0,
                recipient_user_id UUID,
                recipient_name VARCHAR DEFAULT 'Member',
                recipient_turn_position INTEGER DEFAULT 1,
                report_data JSONB DEFAULT '{}',
                ledger_entries_count INTEGER DEFAULT 0,
                cryptographic_hash_sha256 VARCHAR,
                certified_by VARCHAR DEFAULT 'Microbond Authoritative Ledger Engine',
                generated_at BIGINT
            );
        '''))

        conn.execute(sa.text('''
            CREATE TABLE IF NOT EXISTS "payoutsignature" (
                id SERIAL PRIMARY KEY,
                group_id VARCHAR,
                payout_id INTEGER,
                signer_user_id UUID,
                signer_role VARCHAR DEFAULT 'SIGNER',
                status VARCHAR DEFAULT 'SIGNED',
                device_fingerprint VARCHAR,
                pin_verified BOOLEAN DEFAULT TRUE,
                notes VARCHAR,
                signature_timestamp BIGINT
            );
        '''))


def downgrade() -> None:
    pass
