from fastapi import APIRouter
from .request_code import router as request_code_router, request_email_recovery_code
from .verify_code import router as verify_code_router, verify_email_recovery_code
from .request_phone_otp import router as request_phone_otp_router, request_recovery_phone_otp
from .confirm_phone import router as confirm_phone_router, confirm_recovery_phone

router = APIRouter(tags=["Account Recovery"])
router.include_router(request_code_router)
router.include_router(verify_code_router)
router.include_router(request_phone_otp_router)
router.include_router(confirm_phone_router)

__all__ = [
    "router",
    "request_email_recovery_code",
    "verify_email_recovery_code",
    "request_recovery_phone_otp",
    "confirm_recovery_phone",
]
