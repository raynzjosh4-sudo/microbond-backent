from fastapi import APIRouter
from .create_event_committee_group import router as create_router, create_event_committee_group
from .get_event_committee_dashboard import router as dashboard_router, get_event_committee_dashboard
from .update_event_committee_settings import router as settings_router, update_event_committee_settings
from .submit_pledge import router as pledge_router, submit_pledge
from .request_disbursement import router as disbursement_router, request_disbursement
from .close_event import router as close_router, close_event

router = APIRouter(prefix="/api/v1/groups/event-committee", tags=["Event Committee Groups"])
router.include_router(create_router)
router.include_router(dashboard_router)
router.include_router(settings_router)
router.include_router(pledge_router)
router.include_router(disbursement_router)
router.include_router(close_router)
router.router = router

__all__ = [
    "router",
    "create_event_committee_group",
    "get_event_committee_dashboard",
    "update_event_committee_settings",
    "submit_pledge",
    "request_disbursement",
    "close_event",
]
