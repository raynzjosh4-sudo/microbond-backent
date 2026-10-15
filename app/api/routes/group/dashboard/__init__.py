from fastapi import APIRouter
from .get_user_group_dashboard_summaries import (
    router as summaries_router,
    get_user_group_dashboard_summaries,
)

router = APIRouter(prefix="/api/v1/groups/dashboard", tags=["Group Dashboard"])
router.include_router(summaries_router)

__all__ = ["router", "get_user_group_dashboard_summaries"]
