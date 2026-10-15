from fastapi import APIRouter
from .get_deposit_info import router as info_router, get_deposit_info
from .calculate_deposit_quote import router as quote_router, calculate_deposit_quote
from .helpers import trigger_post_deposit_notifications

router = APIRouter(prefix="/api/v1/groups", tags=["Group Deposit Pipeline"])
router.include_router(info_router)
router.include_router(quote_router)

__all__ = [
    "router",
    "get_deposit_info",
    "calculate_deposit_quote",
    "trigger_post_deposit_notifications",
]
