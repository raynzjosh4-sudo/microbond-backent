import json
import logging
import uuid
from typing import Optional, Any
from sqlmodel import Session, select, desc
from app.models.infrastructure.audit_event import AuditEvent
from app.core.microbond_core import canonical_audit_hash

logger = logging.getLogger(__name__)


class AuditService:
    """
    Authoritative service for writing tamper-evident audit records.
    Every financial transition or membership state mutation writes an immutable event.
    """

    @staticmethod
    def record_event(
        session: Session,
        action: str,
        entity_type: str,
        entity_id: str,
        payload: Any,
        actor_user_id: Optional[uuid.UUID] = None,
    ) -> AuditEvent:
        """
        Appends an immutable audit event to the database with cryptographically chained SHA-256 hash.
        Must be called within an active transaction.
        """
        # 1. Fetch the most recent event's hash to chain from
        latest_event = session.exec(
            select(AuditEvent).order_by(desc(AuditEvent.created_at)).limit(1)
        ).first()

        previous_hash = latest_event.current_hash if latest_event else ("0" * 64)

        # 2. Serialize payload deterministically
        payload_json = json.dumps(payload, default=str, sort_keys=True)

        # 3. Compute SHA-256 hash using microbond_core
        current_hash = canonical_audit_hash(previous_hash, payload_json)

        # 4. Persist
        audit_event = AuditEvent(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id),
            payload_json=payload_json,
            previous_hash=previous_hash,
            current_hash=current_hash,
        )
        session.add(audit_event)
        return audit_event
