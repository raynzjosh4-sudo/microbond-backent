from fastapi import APIRouter
from .create_fundraiser import router as create_router, create_fundraiser
from .get_fundraiser_dashboard import router as dashboard_router, get_fundraiser_dashboard
from .update_fundraiser_settings import router as settings_router, update_fundraiser_settings
from .close_campaign import router as close_router, close_campaign
from .request_signoff import router as signoff_router, request_signoff
from .release_funds import router as release_router, release_funds

router = APIRouter(prefix="/api/v1/groups/fundraiser", tags=["Fundraiser Groups"])
router.include_router(create_router)
router.include_router(dashboard_router)
router.include_router(settings_router)
router.include_router(close_router)
router.include_router(signoff_router)
router.include_router(release_router)
router.router = router

__all__ = [
    "router",
    "create_fundraiser",
    "get_fundraiser_dashboard",
    "update_fundraiser_settings",
    "close_campaign",
    "request_signoff",
    "release_funds",
]
