"""
security facade — redirects to app.core.security
"""
from app.core.security import (
    create_access_token,
    hash_pin,
    verify_pin,
    revoke_token,
    revoke_all_user_tokens,
    is_token_revoked,
)

__all__ = [
    "create_access_token",
    "hash_pin",
    "verify_pin",
    "revoke_token",
    "revoke_all_user_tokens",
    "is_token_revoked",
]
