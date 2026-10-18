from fastapi import APIRouter
from .get_privacy_settings import router as get_router, get_user_privacy_settings
from .update_privacy_settings import (
    router as update_router,
    update_user_privacy_settings,
)

router = APIRouter(prefix="/api/v1/users", tags=["User Privacy & Personal Data"])
router.include_router(get_router)
router.include_router(update_router)

__all__ = [
    "router",
    "get_user_privacy_settings",
    "update_user_privacy_settings",
]
