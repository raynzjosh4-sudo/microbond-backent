from fastapi import APIRouter
from .request_otp import router as request_otp_router
from .verify_otp import router as verify_otp_router

router = APIRouter()
router.include_router(request_otp_router)
router.include_router(verify_otp_router)

__all__ = ["router", "request_otp_router", "verify_otp_router"]
