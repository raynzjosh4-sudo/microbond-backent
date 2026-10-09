from fastapi import Request, HTTPException, status
from redis.asyncio import Redis
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize a global Redis connection for rate limiting
redis_client = None

try:
    if settings.REDIS_URL:
        redis_client = Redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
except Exception as e:
    logger.error(f"Failed to initialize Redis Rate Limiter: {e}")

def RateLimiter(times: int, seconds: int):
    """
    A robust Redis-based rate limiter dependency.
    If Redis is down or unavailable (e.g. local development without Redis),
    it logs a warning and allows the request through so development isn't blocked.
    """
    async def _rate_limit(request: Request):
        if not redis_client:
            # Fallback for local development when Redis is not running
            return
        
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        key = f"rate_limit:{path}:{client_ip}"
        
        try:
            count = await redis_client.incr(key)
            if count == 1:
                # First hit in this window -> start the window timer
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
            # If Redis is unreachable, fail open so the app doesn't hard-crash
            logger.warning(f"Rate limiter unavailable, allowing request: {e}")

    return _rate_limit
