from typing import Optional, Any
from dataclasses import dataclass
import json
import uuid
from sqlmodel import Session, select
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from app.models.infrastructure.idempotency import CommandIdempotency


@dataclass(frozen=True)
class CachedCommand:
    response_code: int
    response_payload: Any


def begin_db_command(
    session: Session,
    user_id: uuid.UUID,
    client_request_id: Optional[str],
) -> Optional[CachedCommand]:
    """Reserve an idempotency key before performing a mutation.

    Returns the previously stored response on a retry, or ``None`` after a
    new PENDING command has been flushed into the current transaction.
    """
    if not client_request_id or not client_request_id.strip():
        return None

    clean_id = client_request_id.strip()
    if len(clean_id) > 128:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="client_request_id must be at most 128 characters.",
        )

    existing = session.exec(
        select(CommandIdempotency)
        .where(
            CommandIdempotency.user_id == user_id,
            CommandIdempotency.client_request_id == clean_id,
        )
        .with_for_update()
    ).first()
    if existing is not None:
        return _cached_or_conflict(existing)

    command = CommandIdempotency(
        user_id=user_id,
        client_request_id=clean_id,
        status="PENDING",
        response_code=200,
        response_json="{}",
    )
    try:
        with session.begin_nested():
            session.add(command)
            session.flush()
    except IntegrityError:
        existing = session.exec(
            select(CommandIdempotency)
            .where(
                CommandIdempotency.user_id == user_id,
                CommandIdempotency.client_request_id == clean_id,
            )
            .with_for_update()
        ).first()
        if existing is None:
            raise
        return _cached_or_conflict(existing)
    return None


def complete_db_command(
    session: Session,
    user_id: uuid.UUID,
    client_request_id: Optional[str],
    response_payload: Any,
    response_code: int = 200,
    status_str: str = "COMPLETED",
) -> None:
    """Store the response for an idempotency reservation in the same transaction."""
    if not client_request_id or not client_request_id.strip():
        return
    command = session.exec(
        select(CommandIdempotency)
        .where(
            CommandIdempotency.user_id == user_id,
            CommandIdempotency.client_request_id == client_request_id.strip(),
        )
        .with_for_update()
    ).first()
    if command is None:
        raise LookupError("Idempotency reservation was not found in the current transaction.")
    command.status = status_str
    command.response_code = response_code
    command.response_json = json.dumps(response_payload, default=str, sort_keys=True)
    session.add(command)


def _cached_or_conflict(existing: CommandIdempotency) -> CachedCommand:
    if existing.status == "PENDING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A request with this client_request_id is currently being processed. Please wait.",
        )
    try:
        payload = json.loads(existing.response_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Stored idempotency response is invalid JSON.") from exc
    return CachedCommand(
        response_code=existing.response_code,
        response_payload=payload,
    )


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
        except (TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Stored idempotency response is invalid JSON.") from exc

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
