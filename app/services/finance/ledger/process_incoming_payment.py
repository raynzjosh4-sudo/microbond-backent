import logging
import uuid
import time
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError

from app.models.group.ledger import LedgerEntry
from app.models.group.wallet import GroupWallet
from app.models.group.finance import MemberObligation

logger = logging.getLogger(__name__)


def process_incoming_payment(
    session: Session,
    group_id: str,
    user_id: uuid.UUID,
    amount: int,
    source_account: str,
    external_ref: str,
    obligation_id: int = None
):
    """
    Safely process an incoming payment via double-entry ledger.
    Locks the cached wallet and obligation rows to prevent race conditions.
    Handles duplicate webhook retries via idempotency on the external_reference_id.
    """
    now_ms = int(time.time() * 1000)

    try:
        with session.begin_nested():
            ledger_entry = LedgerEntry(
                group_id=group_id,
                user_id=user_id,
                obligation_id=obligation_id,
                source_account=source_account,
                destination_account="GROUP_POOLED",
                amount=amount,
                transaction_type="DEPOSIT",
                external_reference_id=external_ref,
                status="SETTLED",
                settled_at=now_ms
            )
            session.add(ledger_entry)
            session.flush()
    except IntegrityError as e:
        err_msg = str(e).lower()
        if "unique" in err_msg or "duplicate" in err_msg:
            logger.warning(f"Idempotency triggered: Duplicate webhook payload received for TXN {external_ref}. Ignoring gracefully.")
            return None
        logger.error(f"IntegrityError in process_incoming_payment for TXN {external_ref}: {e}")
        raise

    wallet = session.exec(
        select(GroupWallet)
        .where(GroupWallet.group_id == group_id)
        .with_for_update()
    ).first()

    if not wallet:
        wallet = GroupWallet(group_id=group_id, pooled_funds=0.0, reserve_funds=0.0)
        session.add(wallet)
        session.flush()

    wallet.pooled_funds += amount
    wallet.updated_at = now_ms

    if obligation_id:
        obligation = session.exec(
            select(MemberObligation)
            .where(MemberObligation.id == obligation_id)
            .with_for_update()
        ).first()

        if obligation:
            obligation.amount_paid += amount
            if obligation.amount_paid >= obligation.amount_due:
                obligation.status = "PAID"
                logger.info(f"Obligation {obligation.id} fully PAID via ledger cache.")
            elif obligation.amount_paid > 0 and obligation.status == "PENDING":
                logger.info(f"Obligation {obligation.id} partially paid. Still owes {obligation.amount_due - obligation.amount_paid}.")

            obligation.updated_at = now_ms
            session.add(obligation)

    return ledger_entry
