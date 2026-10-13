from fastapi import APIRouter
from .upload_user_avatar import router as upload_router, upload_user_avatar
from .remove_user_avatar import router as remove_router, remove_user_avatar
from .update_avatar_color import router as color_router, update_avatar_color

router = APIRouter(prefix="/api/v1/users", tags=["Users"])
router.include_router(upload_router)
router.include_router(remove_router)
router.include_router(color_router)

__all__ = [
    "router",
    "upload_user_avatar",
    "remove_user_avatar",
    "update_avatar_color",
]
