import json
import logging
from typing import Optional
from fastapi import Header, HTTPException, status
from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)


async def check_idempotency_header(
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
) -> Optional[str]:
    """
    FastAPI dependency for mutation routes (e.g. mobile money deposit execution).
    When an Idempotency-Key is provided by the client (such as Android app on retry):
    - Atomically sets a PENDING lock in Redis with a 24-hour expiration (86400s).
    - If a request with this key is already active, returns HTTP 409 Conflict.
    - If a previous request completed, raises HTTP 200 with the cached response payload.
    - If no key is supplied, passes through.
    """
    if not idempotency_key or not idempotency_key.strip():
        return None

    clean_key = idempotency_key.strip()
    redis_client = get_redis_client()
    if not redis_client:
        return clean_key

    redis_key = f"idempotency:{clean_key}"

    try:
        # Atomic SET NX with 24-hour TTL
        acquired = await redis_client.set(
            redis_key,
            json.dumps({"status": "PENDING"}),
            ex=86400,
            nx=True
        )

        if not acquired:
            cached_raw = await redis_client.get(redis_key)
            if cached_raw:
                data = json.loads(cached_raw)
                if data.get("status") == "PENDING":
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="A transaction with this Idempotency-Key is currently processing. Please wait for completion."
                    )
                if data.get("status") == "COMPLETED" and "response" in data:
                    raise HTTPException(
                        status_code=status.HTTP_200_OK,
                        detail=data["response"]
                    )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[Idempotency] Failed reading idempotency cache: {e}")

    return clean_key


async def store_idempotent_response(
    idempotency_key: Optional[str],
    response_payload: dict,
    ttl_seconds: int = 86400
):
    """
    Caches the final successful response payload under the given Idempotency-Key.
    Future duplicate calls within ttl_seconds will safely replay this response.
    """
    if not idempotency_key:
        return

    redis_client = get_redis_client()
    if not redis_client:
        return

    redis_key = f"idempotency:{idempotency_key.strip()}"
    try:
        await redis_client.set(
            redis_key,
            json.dumps({"status": "COMPLETED", "response": response_payload}),
            ex=ttl_seconds
        )
    except Exception as e:
        logger.warning(f"[Idempotency] Failed storing response for key {idempotency_key}: {e}")
