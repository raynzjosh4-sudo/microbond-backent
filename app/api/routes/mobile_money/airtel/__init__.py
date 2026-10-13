from fastapi import APIRouter
from .airtel_status import router as status_router, airtel_status

router = APIRouter(prefix="/airtel", tags=["Mobile Money (Airtel)"])
router.include_router(status_router)

__all__ = ["router", "airtel_status"]
