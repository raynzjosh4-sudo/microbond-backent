from fastapi import APIRouter
from .send_chat_message import router as send_chat_message_router, send_chat_message
from .get_chat_messages import router as get_chat_messages_router, get_chat_messages
from .helpers import broadcast_system_message_sync

router = APIRouter(prefix="/api/v1/groups", tags=["Group Chat"])
router.include_router(send_chat_message_router)
router.include_router(get_chat_messages_router)
router.router = router

__all__ = [
    "router",
    "send_chat_message",
    "get_chat_messages",
    "broadcast_system_message_sync",
]
