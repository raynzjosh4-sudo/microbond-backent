import os
import threading
from sqlmodel import SQLModel
from app.core.database.engine import engine


def _run_migrations():
    """Run Alembic migrations programmatically to apply pending schema changes and new columns."""
    try:
        from alembic.config import Config
        from alembic import command

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        ini_path = os.path.join(base_dir, "alembic.ini")
        if not os.path.exists(ini_path):
            ini_path = os.path.abspath("alembic.ini")

        if os.path.exists(ini_path):
            alembic_cfg = Config(ini_path)
            command.upgrade(alembic_cfg, "head")
            print("[Alembic] Successfully ran database migrations up to head.")
        else:
            print(f"[Alembic warning] alembic.ini not found at {ini_path}, skipping programmatic migration.")
    except Exception as e:
        print(f"[Alembic warning] Could not run automatic migrations: {e}")


def _run_create_all():
    try:
        # Import all models to ensure SQLModel registers them before create_all
        import app.models.user.user
        import app.models.user.security_email
        import app.models.user.kyc
        import app.models.user.invite
        import app.models.user.userpayoutaccount.payout_destination
        import app.models.user.userpaymentmethod.payment_method
        import app.models.auth.otp
        import app.models.group.group
        import app.models.group.settings
        import app.models.group.rotating
        import app.models.group.long_term
        import app.models.group.welfare_event
        import app.models.group.investment_association
        import app.models.group.bill_split
        import app.models.group.report
        import app.models.infrastructure

        SQLModel.metadata.create_all(engine)
    except Exception as e:
        print(f"[init_db warning] Skipping create_all due to: {e}")

    # Automatically run migrations so new columns on existing tables are applied
    _run_migrations()


def _ensure_critical_columns():
    """Idempotently adds missing settings columns in PostgreSQL if not present."""
    from sqlalchemy import text
    try:
        sql_statements = [
            # groupcommunicationsettings
            'ALTER TABLE "groupcommunicationsettings" ADD COLUMN IF NOT EXISTS "send_dues_due_prompts" BOOLEAN NOT NULL DEFAULT TRUE;',
            'ALTER TABLE "groupcommunicationsettings" ADD COLUMN IF NOT EXISTS "send_loan_due_prompts" BOOLEAN NOT NULL DEFAULT TRUE;',
            'ALTER TABLE "groupcommunicationsettings" ADD COLUMN IF NOT EXISTS "broadcast_individual_dues_receipts" BOOLEAN NOT NULL DEFAULT TRUE;',
            'ALTER TABLE "groupcommunicationsettings" ADD COLUMN IF NOT EXISTS "broadcast_individual_loan_receipts" BOOLEAN NOT NULL DEFAULT TRUE;',
            'ALTER TABLE "groupcommunicationsettings" ADD COLUMN IF NOT EXISTS "announce_dues_adjustment_updates" BOOLEAN NOT NULL DEFAULT TRUE;',
            'ALTER TABLE "groupcommunicationsettings" ADD COLUMN IF NOT EXISTS "announce_loan_disbursement_updates" BOOLEAN NOT NULL DEFAULT TRUE;',
            'ALTER TABLE "groupcommunicationsettings" ADD COLUMN IF NOT EXISTS "post_loan_approval_polls" BOOLEAN NOT NULL DEFAULT TRUE;',
            'ALTER TABLE "groupcommunicationsettings" ADD COLUMN IF NOT EXISTS "enable_automated_audit_dispatch" BOOLEAN NOT NULL DEFAULT TRUE;',
            'ALTER TABLE "groupcommunicationsettings" ADD COLUMN IF NOT EXISTS "audit_report_recipient_email" VARCHAR;',
            'ALTER TABLE "groupcommunicationsettings" ADD COLUMN IF NOT EXISTS "dispatch_monthly_compliance_statement" BOOLEAN NOT NULL DEFAULT TRUE;',
            'ALTER TABLE "groupcommunicationsettings" ADD COLUMN IF NOT EXISTS "export_file_format" VARCHAR NOT NULL DEFAULT \'PDF\';',

            # groupvisibilitysettings
            'ALTER TABLE "groupvisibilitysettings" ADD COLUMN IF NOT EXISTS "vis_member_total_savings" BOOLEAN NOT NULL DEFAULT TRUE;',
            'ALTER TABLE "groupvisibilitysettings" ADD COLUMN IF NOT EXISTS "vis_dues_schedule" BOOLEAN NOT NULL DEFAULT FALSE;',
            'ALTER TABLE "groupvisibilitysettings" ADD COLUMN IF NOT EXISTS "vis_allow_installments" BOOLEAN NOT NULL DEFAULT FALSE;',
            'ALTER TABLE "groupvisibilitysettings" ADD COLUMN IF NOT EXISTS "vis_arrears_policy" BOOLEAN NOT NULL DEFAULT FALSE;',
            'ALTER TABLE "groupvisibilitysettings" ADD COLUMN IF NOT EXISTS "vis_fee_exemptions" BOOLEAN NOT NULL DEFAULT FALSE;',
            'ALTER TABLE "groupvisibilitysettings" ADD COLUMN IF NOT EXISTS "vis_interest_rates" BOOLEAN NOT NULL DEFAULT FALSE;',
            'ALTER TABLE "groupvisibilitysettings" ADD COLUMN IF NOT EXISTS "vis_loan_guarantor_rules" BOOLEAN NOT NULL DEFAULT FALSE;',
            'ALTER TABLE "groupvisibilitysettings" ADD COLUMN IF NOT EXISTS "vis_max_borrowing_limit" BOOLEAN NOT NULL DEFAULT FALSE;',
            'ALTER TABLE "groupvisibilitysettings" ADD COLUMN IF NOT EXISTS "vis_early_repayment_discount" BOOLEAN NOT NULL DEFAULT FALSE;',
            'ALTER TABLE "groupvisibilitysettings" ADD COLUMN IF NOT EXISTS "vis_new_share_issuance" BOOLEAN NOT NULL DEFAULT FALSE;',
            'ALTER TABLE "groupvisibilitysettings" ADD COLUMN IF NOT EXISTS "vis_default_asset_seizure" BOOLEAN NOT NULL DEFAULT FALSE;',
            'ALTER TABLE "groupvisibilitysettings" ADD COLUMN IF NOT EXISTS "vis_pending_dues_adjustments" BOOLEAN NOT NULL DEFAULT FALSE;',
            'ALTER TABLE "groupvisibilitysettings" ADD COLUMN IF NOT EXISTS "vis_pending_loans" BOOLEAN NOT NULL DEFAULT FALSE;',
            'ALTER TABLE "groupvisibilitysettings" ADD COLUMN IF NOT EXISTS "vis_auto_debit_consent" BOOLEAN NOT NULL DEFAULT FALSE;',
            'ALTER TABLE "groupvisibilitysettings" ADD COLUMN IF NOT EXISTS "vis_emergency_contact" BOOLEAN NOT NULL DEFAULT FALSE;',
            'ALTER TABLE "groupvisibilitysettings" ADD COLUMN IF NOT EXISTS "vis_sms_call_reminders" BOOLEAN NOT NULL DEFAULT FALSE;',
            'ALTER TABLE "groupvisibilitysettings" ADD COLUMN IF NOT EXISTS "vis_broadcast_individual_dues_receipts" BOOLEAN NOT NULL DEFAULT TRUE;',
            'ALTER TABLE "groupvisibilitysettings" ADD COLUMN IF NOT EXISTS "vis_broadcast_individual_loan_receipts" BOOLEAN NOT NULL DEFAULT TRUE;',
            'ALTER TABLE "groupvisibilitysettings" ADD COLUMN IF NOT EXISTS "vis_announce_dues_adjustment_updates" BOOLEAN NOT NULL DEFAULT TRUE;',
            'ALTER TABLE "groupvisibilitysettings" ADD COLUMN IF NOT EXISTS "vis_announce_loan_disbursement_updates" BOOLEAN NOT NULL DEFAULT TRUE;',
            'ALTER TABLE "groupvisibilitysettings" ADD COLUMN IF NOT EXISTS "vis_send_dues_due_prompts" BOOLEAN NOT NULL DEFAULT TRUE;',
            'ALTER TABLE "groupvisibilitysettings" ADD COLUMN IF NOT EXISTS "vis_send_loan_due_prompts" BOOLEAN NOT NULL DEFAULT TRUE;',
            'ALTER TABLE "groupvisibilitysettings" ADD COLUMN IF NOT EXISTS "vis_post_loan_approval_polls" BOOLEAN NOT NULL DEFAULT TRUE;',
            'ALTER TABLE "groupfinancialsettings" ADD COLUMN IF NOT EXISTS "enforce_payout_holds" BOOLEAN NOT NULL DEFAULT FALSE;',
            'ALTER TABLE "groupreport" ADD COLUMN IF NOT EXISTS "reported_user_id" UUID;',
            'ALTER TABLE "groupmembership" ADD COLUMN IF NOT EXISTS "credit_balance_ugx" BIGINT NOT NULL DEFAULT 0;',
            'ALTER TABLE "groupwallet" ADD COLUMN IF NOT EXISTS "prepaid_funds" BIGINT NOT NULL DEFAULT 0;',

            # rotatinggroupdetails
            'ALTER TABLE "rotatinggroupdetails" ADD COLUMN IF NOT EXISTS "auto_disburse_when_full" BOOLEAN NOT NULL DEFAULT TRUE;',
            'ALTER TABLE "rotatinggroupdetails" ADD COLUMN IF NOT EXISTS "multi_sig_payout_approval" BOOLEAN NOT NULL DEFAULT FALSE;',
            'ALTER TABLE "rotatinggroupdetails" ADD COLUMN IF NOT EXISTS "allow_turn_swaps" BOOLEAN NOT NULL DEFAULT TRUE;',
            'ALTER TABLE "rotatinggroupdetails" ADD COLUMN IF NOT EXISTS "turn_swap_approval_mode" VARCHAR NOT NULL DEFAULT \'MUTUAL_CONSENT\';',
            'ALTER TABLE "rotatinggroupdetails" ADD COLUMN IF NOT EXISTS "early_turn_security_hold_percentage" DOUBLE PRECISION NOT NULL DEFAULT 0.0;',
            'ALTER TABLE "rotatinggroupdetails" ADD COLUMN IF NOT EXISTS "require_guarantors_for_early_turns_only" BOOLEAN NOT NULL DEFAULT TRUE;',
            'ALTER TABLE "rotatinggroupdetails" ADD COLUMN IF NOT EXISTS "auto_renew_cycle" BOOLEAN NOT NULL DEFAULT FALSE;',
            'ALTER TABLE "rotatinggroupdetails" ADD COLUMN IF NOT EXISTS "reverse_payout_order_on_renew" BOOLEAN NOT NULL DEFAULT TRUE;',
            'ALTER TABLE "rotatinggroupdetails" ADD COLUMN IF NOT EXISTS "reminder_lead_time_hours" INTEGER NOT NULL DEFAULT 24;',
            'ALTER TABLE "rotatinggroupdetails" ADD COLUMN IF NOT EXISTS "enable_auto_debit_prompt" BOOLEAN NOT NULL DEFAULT TRUE;',
            'ALTER TABLE "rotatinggroupdetails" ADD COLUMN IF NOT EXISTS "current_cycle" INTEGER NOT NULL DEFAULT 1;',
            'ALTER TABLE "rotatinggroupdetails" ADD COLUMN IF NOT EXISTS "saving_days_per_cycle" INTEGER;',
            'ALTER TABLE "rotatinggroupdetails" ADD COLUMN IF NOT EXISTS "current_saving_day" INTEGER NOT NULL DEFAULT 0;',
            'ALTER TABLE "rotatinggroupdetails" ADD COLUMN IF NOT EXISTS "minimum_partial_payment_amount" DOUBLE PRECISION;',
            'ALTER TABLE "memberobligation" ADD COLUMN IF NOT EXISTS "last_reminder_tier" INTEGER;',
            '''CREATE TABLE IF NOT EXISTS "rotatingcyclereport" (
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
            );''',
            '''CREATE TABLE IF NOT EXISTS "payoutsignature" (
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
            );''',
        ]

        is_postgres = getattr(engine.dialect, "name", "") == "postgresql"
        for stmt in sql_statements:
            try:
                with engine.connect() as conn:
                    if is_postgres:
                        conn.execution_options(isolation_level="AUTOCOMMIT").execute(text(stmt))
                    else:
                        conn.execute(text(stmt))
                        conn.commit()
            except Exception:
                pass
        print("[init_db] Ensured all critical settings columns exist in database.")
    except Exception as e:
        print(f"[init_db warning] Column reconciliation skipped or non-Postgres: {e}")


def init_db():
    """Run DDL check and migrations so tables and columns exist before handling requests."""
    _run_create_all()
    _ensure_critical_columns()
