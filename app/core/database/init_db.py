import threading
from sqlmodel import SQLModel
from app.core.database.engine import engine


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


def init_db():
    """Run DDL check asynchronously in background to ensure uvicorn restarts instantly."""
    threading.Thread(target=_run_create_all, daemon=True).start()
