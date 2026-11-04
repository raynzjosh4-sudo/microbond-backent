"""
database facade — redirects to app.core.database
"""
from app.core.database import (
    engine,
    init_db,
    _ensure_critical_columns,
    get_session,
)

__all__ = [
    "engine",
    "init_db",
    "_ensure_critical_columns",
    "get_session",
]
