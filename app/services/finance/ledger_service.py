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
    
    # 1. Idempotency Check & Ledger Insertion
    # We wrap this in a SAVEPOINT (nested transaction) so if it fails, it only 
    # rolls back the savepoint, leaving the caller's main transaction intact.
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
            session.flush() # Force DB to evaluate the unique constraint immediately
    except IntegrityError:
        logger.warning(f"Idempotency triggered: Duplicate webhook payload received for TXN {external_ref}. Ignoring gracefully.")
        # Returning None signals the caller to return a 200 OK so the telecom stops retrying.
        return None

    
    # 2. Update the Wallet Cache (with strict row locking)
    wallet = session.exec(
        select(GroupWallet)
        .where(GroupWallet.group_id == group_id)
        .with_for_update()
    ).first()
    
    if not wallet:
        wallet = GroupWallet(group_id=group_id, pooled_funds=0.0, reserve_funds=0.0)
        session.add(wallet)
        # Flush to get the lock on the newly created row before updating
        session.flush() 
        
    wallet.pooled_funds += amount
    wallet.updated_at = now_ms
    
    # 3. Handle Partial / Full Obligation Updates
    if obligation_id:
        obligation = session.exec(
            select(MemberObligation)
            .where(MemberObligation.id == obligation_id)
            .with_for_update()
        ).first()
        
        if obligation:
            # We treat amount_paid as a cache of the ledger sums.
            obligation.amount_paid += amount
            
            # Re-evaluate status based on the true due amount
            if obligation.amount_paid >= obligation.amount_due:
                obligation.status = "PAID"
                logger.info(f"Obligation {obligation.id} fully PAID via ledger cache.")
            elif obligation.amount_paid > 0 and obligation.status == "PENDING":
                # It's a partial payment. We leave it as PENDING (or you could use a PARTIALLY_PAID status).
                # The late fee cron handles partial payments correctly because it looks at `amount_paid < amount_due`.
                logger.info(f"Obligation {obligation.id} partially paid. Still owes {obligation.amount_due - obligation.amount_paid}.")
                
            obligation.updated_at = now_ms
            session.add(obligation)

    # 4. Return ledger entry and schedule real-time WebSocket broadcast
    # Caller commits the transaction and invokes broadcast_group_ring_update
    return ledger_entry

async def broadcast_group_ring_update(group_id: str, depositor_name: str, amount: int):
    """
    Pushes real-time RING_STATUS_UPDATED event over WebSockets to all connected group members.
    Advances the green arc and pushes the new action ticker message in 0ms.
    """
    from app.core.database import engine
    from app.services.websocket_manager import manager
    from app.services.group.dashboard_summary_service import GroupDashboardSummaryService
    
    with Session(engine) as session:
        ring = GroupDashboardSummaryService.calculate_group_ring(session, group_id)
        
        payload = {
            "event_type": "RING_STATUS_UPDATED",
            "group_id": group_id,
            "ring_status": ring.model_dump(),
            "new_action_message": {
                "text": f"{depositor_name} deposited {amount:,} UGX",
                "type": "RECENT_CONTRIBUTION",
                "has_blue_ticks": True,
                "is_alert": False
            }
        }
        await manager.broadcast_to_group(group_id=group_id, message=payload)

