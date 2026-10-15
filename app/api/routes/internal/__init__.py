from fastapi import APIRouter
from .launch_groups import router as launch_groups_router, launch_groups
from .process_payouts import router as process_payouts_router, process_payouts
from .process_late_fees import router as process_late_fees_router, process_late_fees
from .process_health_ratings import router as process_health_ratings_router, process_health_ratings
from .send_email import router as send_email_router, send_email
from .send_push import router as send_push_router, send_push
from .send_sms import router as send_sms_router, send_sms

router = APIRouter(prefix="/api/v1/internal/tasks", tags=["Internal Tasks"])

router.include_router(launch_groups_router)
router.include_router(process_payouts_router)
router.include_router(process_late_fees_router)
router.include_router(process_health_ratings_router)
router.include_router(send_email_router)
router.include_router(send_push_router)
router.include_router(send_sms_router)

router.router = router

__all__ = [
    "router",
    "launch_groups",
    "process_payouts",
    "process_late_fees",
    "process_health_ratings",
    "send_email",
    "send_push",
    "send_sms",
]
