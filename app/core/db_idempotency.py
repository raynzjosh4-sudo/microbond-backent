from typing import Optional, Any
import json
import uuid
from sqlmodel import Session
from fastapi import HTTPException, status
from app.models.infrastructure.idempotency import CommandIdempotency


def check_db_idempotency(
    session: Session,
    user_id: uuid.UUID,
    client_request_id: Optional[str]
) -> Optional[dict]:
    """
    Checks if a command with (user_id, client_request_id) has already been executed.
    Locks the existing row with FOR UPDATE.
    Returns the cached response dict if already processed, or raises HTTP 409 if currently pending.
    """
    if not client_request_id or not client_request_id.strip():
        return None

    clean_id = client_request_id.strip()
    from sqlmodel import select
    existing = session.exec(
        select(CommandIdempotency)
        .where(
            CommandIdempotency.user_id == user_id,
            CommandIdempotency.client_request_id == clean_id
        )
        .with_for_update()
    ).first()

    if existing:
        if existing.status == "PENDING":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A request with this client_request_id is currently being processed. Please wait."
            )
        try:
            return json.loads(existing.response_json)
        except Exception:
            return {"status": existing.status}

    return None


def record_db_idempotency(
    session: Session,
    user_id: uuid.UUID,
    client_request_id: Optional[str],
    response_payload: Any,
    response_code: int = 200,
    status_str: str = "COMPLETED"
):
    """
    Persists the authoritative response for this client_request_id inside the active transaction.
    """
    if not client_request_id or not client_request_id.strip():
        return

    clean_id = client_request_id.strip()
    payload_json = json.dumps(response_payload, default=str)

    idemp_row = CommandIdempotency(
        user_id=user_id,
        client_request_id=clean_id,
        status=status_str,
        response_code=response_code,
        response_json=payload_json
    )
    session.add(idemp_row)
