from fastapi import APIRouter
from .otp import router as otp_router
from .account_recovery import router as account_recovery_router

router = APIRouter()
router.include_router(otp_router)
router.include_router(account_recovery_router)

__all__ = ["router", "otp_router", "account_recovery_router"]
