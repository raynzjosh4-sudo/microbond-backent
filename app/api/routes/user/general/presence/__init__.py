from fastapi import APIRouter
from .send_user_heartbeat import (
    router as heartbeat_router,
    send_user_heartbeat,
)
from .get_user_presence import router as presence_router, get_user_presence
from .get_group_members_presence import (
    router as group_presence_router,
    get_group_members_presence,
)

router = APIRouter(prefix="/api/v1/users", tags=["Users Presence & Activity"])
router.include_router(heartbeat_router)
router.include_router(presence_router)
router.include_router(group_presence_router)

__all__ = [
    "router",
    "send_user_heartbeat",
    "get_user_presence",
    "get_group_members_presence",
]
