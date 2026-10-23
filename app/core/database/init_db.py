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


def init_db():
    """Run DDL check and migrations so tables and columns exist before handling requests."""
    _run_create_all()
