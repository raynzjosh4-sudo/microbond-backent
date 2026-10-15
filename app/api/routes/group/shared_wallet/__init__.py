from fastapi import APIRouter
from .create_shared_wallet_group import router as create_router, create_shared_wallet_group
from .get_shared_wallet_dashboard import router as dashboard_router, get_shared_wallet_dashboard
from .update_shared_wallet_settings import router as settings_router, update_shared_wallet_settings
from .request_spend import router as spend_router, request_spend
from .approve_spend import router as approve_router, approve_spend
from .execute_spend import router as execute_router, execute_spend

router = APIRouter(prefix="/api/v1/groups/shared-wallet", tags=["Shared Wallet Groups"])
router.include_router(create_router)
router.include_router(dashboard_router)
router.include_router(settings_router)
router.include_router(spend_router)
router.include_router(approve_router)
router.include_router(execute_router)
router.router = router

__all__ = [
    "router",
    "create_shared_wallet_group",
    "get_shared_wallet_dashboard",
    "update_shared_wallet_settings",
    "request_spend",
    "approve_spend",
    "execute_spend",
]
