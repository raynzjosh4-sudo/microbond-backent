from fastapi import APIRouter
from .mtn_status import router as status_router, mtn_status

router = APIRouter(prefix="/mtn", tags=["Mobile Money (MTN)"])
router.include_router(status_router)

__all__ = ["router", "mtn_status"]
