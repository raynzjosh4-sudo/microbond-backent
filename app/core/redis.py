import logging
from typing import Optional
from redis.asyncio import Redis, ConnectionPool
from app.core.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[ConnectionPool] = None
_client: Optional[Redis] = None


def get_redis_client() -> Optional[Redis]:
    """
    Returns a shared, pooled asynchronous Redis client.
    Reused across rate limiting, idempotency checks, and WebSocket manager.
    """
    global _pool, _client
    if _client is not None:
        return _client

    if not settings.REDIS_URL:
        return None

    try:
        _pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20
        )
        _client = Redis(connection_pool=_pool)
        return _client
    except Exception as e:
        logger.warning(f"[Redis] Could not initialize connection pool: {e}")
        return None
