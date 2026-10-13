"""
security facade — redirects to app.core.security
"""
from app.core.security import (
    create_access_token,
    hash_pin,
    verify_pin,
)

__all__ = [
    "create_access_token",
    "hash_pin",
    "verify_pin",
]
