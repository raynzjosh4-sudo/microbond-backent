from fastapi import APIRouter
from .get_user_status import router as status_router, get_user_status
from .get_current_user_profile import (
    router as me_router,
    get_current_user_profile,
)
from .get_allowed_groups import (
    router as allowed_groups_router,
    get_allowed_groups,
)
from .update_current_user_profile import (
    router as update_profile_router,
    update_current_user_profile,
)
from .update_current_user_name import (
    router as update_name_router,
    update_current_user_name,
)
from .update_user_name_by_id import (
    router as update_name_id_router,
    update_user_name_by_id,
)

router = APIRouter(prefix="/api/v1/users", tags=["Users"])
router.include_router(status_router)
router.include_router(me_router)
router.include_router(allowed_groups_router)
router.include_router(update_profile_router)
router.include_router(update_name_router)
router.include_router(update_name_id_router)

__all__ = [
    "router",
    "get_user_status",
    "get_current_user_profile",
    "get_allowed_groups",
    "update_current_user_profile",
    "update_current_user_name",
    "update_user_name_by_id",
]
