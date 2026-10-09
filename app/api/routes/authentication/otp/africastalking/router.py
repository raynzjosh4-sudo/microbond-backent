from fastapi import APIRouter

from .request_otp import router as request_otp_router
from .verify_otp import router as verify_otp_router
from .delivery_report import router as delivery_router

router = APIRouter(
    prefix="/api/v1/auth/at-otp", tags=["Authentication (Africa's Talking)"]
)

# Include all the modularized routes
router.include_router(request_otp_router)
router.include_router(verify_otp_router)
router.include_router(delivery_router)
