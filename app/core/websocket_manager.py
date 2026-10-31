"""
websocket_manager facade — re-exports ws_manager and manager from app.services.websocket_manager
"""
from app.services.websocket_manager import (
    ConnectionManager,
    ws_manager,
    manager,
)

__all__ = [
    "ConnectionManager",
    "ws_manager",
    "manager",
]
