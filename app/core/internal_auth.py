import logging
from typing import Optional
from fastapi import Header, HTTPException, status
from app.core.config import settings

logger = logging.getLogger(__name__)


def verify_internal_task_request(
    x_internal_secret: Optional[str] = Header(None, alias="X-Internal-Secret"),
    authorization: Optional[str] = Header(None)
) -> bool:
    """
    Validates that incoming requests to /api/v1/internal/tasks/* are legitimate
    and originated from Google Cloud Scheduler or Google Cloud Tasks.

    Security logic:
    1. If INTERNAL_TASKS_KEY is configured in environment / secrets:
       - Matches X-Internal-Secret header OR
       - Matches Bearer token in Authorization header (OIDC token or shared secret).
       - Rejects with 401 if missing or invalid.
    2. If INTERNAL_TASKS_KEY is NOT set:
       - Only permits execution if ENVIRONMENT == 'development' (for local testing).
       - Fails closed with 403 in staging/production to prevent unauthenticated execution.
    """
    expected_secret = settings.INTERNAL_TASKS_KEY.strip() if settings.INTERNAL_TASKS_KEY else None

    if expected_secret:
        if x_internal_secret and x_internal_secret.strip() == expected_secret:
            return True

        if authorization and authorization.startswith("Bearer "):
            token = authorization.split(" ", 1)[1].strip()
            if token == expected_secret:
                return True

        logger.warning("[InternalAuth] Unauthorized attempt to invoke internal task endpoint.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing internal task authentication credentials."
        )

    # If no secret configured:
    if settings.ENVIRONMENT != "development":
        logger.error("[InternalAuth] INTERNAL_TASKS_KEY is missing in non-development environment.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Internal task endpoints are locked. INTERNAL_TASKS_KEY must be configured."
        )

    # In local development without a configured key, allow with a log notice
    logger.debug("[InternalAuth] Allowing unauthenticated internal task call in development mode.")
    return True
