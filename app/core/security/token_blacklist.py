import hashlib
import time
import logging
from typing import Optional, Dict, Any

try:
    import redis
except ImportError:
    redis = None

from app.core.config import settings

logger = logging.getLogger(__name__)

# L1 In-Memory Cache for revoked tokens: token_hash -> expire_timestamp (epoch seconds)
_memory_blacklist: Dict[str, float] = {}
# L1 In-Memory User Revocation: user_id -> revoked_after_timestamp (epoch seconds)
_user_revocation_memory: Dict[str, float] = {}

_sync_redis_client: Optional[Any] = None
_redis_last_failure_time: float = 0.0
_REDIS_FAILURE_COOLDOWN: float = 30.0  # Cooldown before retrying if Redis is down


def get_sync_redis() -> Optional[Any]:
    """
    Returns a pooled synchronous Redis client with short timeouts.
    If Redis is down or unreachable, sets a cooldown and returns None gracefully.
    """
    if redis is None:
        return None
    global _sync_redis_client, _redis_last_failure_time
    now = time.time()
    if now - _redis_last_failure_time < _REDIS_FAILURE_COOLDOWN:
        return None

    if _sync_redis_client is not None:
        return _sync_redis_client

    if not getattr(settings, "REDIS_URL", None):
        return None

    try:
        _sync_redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
        # Verify connection
        _sync_redis_client.ping()
        return _sync_redis_client
    except Exception as e:
        _redis_last_failure_time = now
        logger.debug(f"[TokenBlacklist] Sync Redis unavailable: {e}. Falling back to in-memory blacklist.")
        return None


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def revoke_token(token: str, expire_seconds: Optional[int] = None) -> bool:
    """
    Revokes a specific JWT token until its natural expiration.
    """
    global _redis_last_failure_time
    now = time.time()
    default_ttl = getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 1440) * 60
    ttl = expire_seconds if (expire_seconds and expire_seconds > 0) else default_ttl
    token_hash = _hash_token(token)

    # 1. Store in Memory
    _prune_memory_blacklist()
    _memory_blacklist[token_hash] = now + ttl

    # 2. Store in Redis (if available)
    client = get_sync_redis()
    if client:
        try:
            client.setex(f"blacklist:token:{token_hash}", int(ttl), "revoked")
            return True
        except Exception as e:
            _redis_last_failure_time = now
            logger.warning(f"[TokenBlacklist] Redis write failed: {e}")

    return True


def revoke_all_user_tokens(user_id: str, expire_seconds: Optional[int] = None) -> bool:
    """
    Revokes all tokens issued for a user up to the current timestamp.
    """
    global _redis_last_failure_time
    now = time.time()
    default_ttl = getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 1440) * 60
    ttl = expire_seconds if (expire_seconds and expire_seconds > 0) else default_ttl

    # 1. Store in Memory
    _user_revocation_memory[str(user_id)] = now

    # 2. Store in Redis (if available)
    client = get_sync_redis()
    if client:
        try:
            client.setex(f"blacklist:user:{user_id}", int(ttl), str(now))
            return True
        except Exception as e:
            _redis_last_failure_time = now
            logger.warning(f"[TokenBlacklist] Redis write user revocation failed: {e}")

    return True


def is_token_revoked(token: str, user_id: Optional[str] = None, token_iat: Optional[float] = None) -> bool:
    """
    Checks whether a token or the user's active sessions have been revoked.
    """
    global _redis_last_failure_time
    if not token:
        return False

    now = time.time()
    token_hash = _hash_token(token)

    # 1. Check in-memory token blacklist
    expiry = _memory_blacklist.get(token_hash)
    if expiry is not None:
        if expiry > now:
            return True
        else:
            _memory_blacklist.pop(token_hash, None)

    # 2. Check in-memory user-level revocation (all sessions logout)
    if user_id:
        user_revoked_at = _user_revocation_memory.get(str(user_id))
        if user_revoked_at is not None:
            # If token was issued at or before the revocation timestamp
            if token_iat is not None and token_iat <= user_revoked_at:
                return True

    # 3. Check Redis (if available)
    client = get_sync_redis()
    if client:
        try:
            val = client.get(f"blacklist:token:{token_hash}")
            if val is not None:
                return True

            if user_id:
                user_val = client.get(f"blacklist:user:{user_id}")
                if user_val is not None:
                    revoked_at = float(user_val)
                    if token_iat is not None and token_iat <= revoked_at:
                        return True
        except Exception as e:
            _redis_last_failure_time = now
            logger.debug(f"[TokenBlacklist] Redis check failed: {e}")

    return False


def _prune_memory_blacklist():
    now = time.time()
    expired_keys = [k for k, exp in _memory_blacklist.items() if exp <= now]
    for k in expired_keys:
        _memory_blacklist.pop(k, None)
