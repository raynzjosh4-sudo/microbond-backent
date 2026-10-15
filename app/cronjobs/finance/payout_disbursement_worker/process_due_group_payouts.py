import logging
import time
from sqlmodel import Session, select
from app.core.database import engine
from app.models.group.finance import GroupPayout
from .process_single_payout import process_single_payout

logger = logging.getLogger(__name__)


def process_due_group_payouts():
    """
    Background worker that runs periodically on APScheduler or Cloud Scheduler.
    Finds all matured group payouts due for disbursement, verifies group rules
    and financial liquidity, resolves each member's chosen destination account,
    and executes telecom B2C payout disbursements.

    Uses row-level locking (with_for_update skip_locked=True) and isolated transactions
    to guarantee zero double-disbursements across multi-instance Cloud Run scaling.
    """
    logger.info("[PAYOUT_WORKER] Checking for due group payouts...")
    now_ms = int(time.time() * 1000)

    # 1. Query pending payout candidate IDs without holding a long database lock
    with Session(engine) as session:
        due_payout_ids = session.exec(
            select(GroupPayout.id)
            .where(
                GroupPayout.status == "PENDING",
                GroupPayout.payout_date <= now_ms
            )
            .order_by(GroupPayout.payout_date.asc())
        ).all()

    if not due_payout_ids:
        logger.info("[PAYOUT_WORKER] No due payouts found.")
        return

    logger.info(f"[PAYOUT_WORKER] Found {len(due_payout_ids)} pending payout candidate(s) ready for disbursement.")

    # 2. Process each payout in its own isolated transaction with skip_locked
    for payout_id in due_payout_ids:
        try:
            with Session(engine) as payout_session:
                # Atomically acquire and lock this payout row
                payout = payout_session.exec(
                    select(GroupPayout)
                    .where(GroupPayout.id == payout_id, GroupPayout.status == "PENDING")
                    .with_for_update(skip_locked=True)
                ).first()

                if not payout:
                    # Payout was already claimed/processed by a concurrent worker
                    logger.info(f"[PAYOUT_WORKER] Payout ID {payout_id} is already claimed by another worker. Skipping.")
                    continue

                # Transition status to PROCESSING atomically so no other worker can touch it
                payout.status = "PROCESSING"
                payout_session.add(payout)
                payout_session.commit()
                payout_session.refresh(payout)

                # Execute single payout disbursement safely
                process_single_payout(payout_session, payout, now_ms)
        except Exception as e:
            logger.exception(f"[PAYOUT_WORKER] Unhandled error processing payout ID {payout_id}: {e}")
