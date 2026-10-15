import hashlib
import logging
from fastapi import Request, HTTPException, status
from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)


def RateLimiter(times: int, seconds: int, fail_open: bool = True, key_prefix: str = ""):
    """
    Robust Redis-backed rate limiter dependency with:
    1. Support for X-Forwarded-For headers from Google Cloud Front End / Cloud Run proxy.
    2. User-specific partitioning via Authorization Bearer token hash to prevent mobile
       carrier NAT IP bottlenecks on MTN and Airtel.
    3. Configurable fail_open: fails closed (fail_open=False) for critical financial actions,
       fails open (fail_open=True) for general queries if Redis is temporarily unreachable.
    """
    async def _rate_limit(request: Request):
        redis_client = get_redis_client()
        if not redis_client:
            if not fail_open:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Rate limiting verification unavailable. Please try again shortly."
                )
            return

        # 1. Determine client identifier:
        # If user has an Authorization token, hash it for user-scoped rate limiting
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            token_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
            client_id = f"user:{token_hash}"
        else:
            # Respect Google Cloud Run / reverse proxy forwarded client IPs
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                client_ip = forwarded.split(",")[0].strip()
            else:
                client_ip = request.client.host if request.client else "unknown"
            client_id = f"ip:{client_ip}"

        path = request.url.path
        prefix = f"{key_prefix}:" if key_prefix else ""
        key = f"rate_limit:{prefix}{path}:{client_id}"

        try:
            count = await redis_client.incr(key)
            if count == 1:
                # First hit in this window -> start expiration timer
                await redis_client.expire(key, seconds)
            if count > times:
                ttl = await redis_client.ttl(key)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                    headers={"Retry-After": str(max(ttl, 1))},
                )
        except HTTPException:
            raise
        except Exception as e:
            if not fail_open:
                logger.error(f"Rate limiter failed closed on critical endpoint: {e}")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Security verification unavailable. Please try again later."
                )
            logger.warning(f"Rate limiter unavailable, allowing request: {e}")

    return _rate_limit
