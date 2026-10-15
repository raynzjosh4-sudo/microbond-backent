from fastapi import APIRouter
from .create_target_savings_group import (
    router as create_router,
    create_target_savings_group,
)
from .get_target_savings_settings import (
    router as get_router,
    get_target_savings_settings,
)
from .update_target_savings_settings import (
    router as update_router,
    update_target_savings_settings,
)
from .request_early_payout import (
    router as early_payout_router,
    request_early_payout,
)

router = APIRouter(prefix="/api/v1/groups/target-savings", tags=["Target Savings Groups"])
router.include_router(create_router)
router.include_router(get_router)
router.include_router(update_router)
router.include_router(early_payout_router)
router.router = router

__all__ = [
    "router",
    "create_target_savings_group",
    "get_target_savings_settings",
    "update_target_savings_settings",
    "request_early_payout",
]
