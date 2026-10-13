from fastapi import APIRouter
from .force_kyc_refresh import router as force_kyc_refresh_router

router = APIRouter(prefix="/api/v1/kyc/phone", tags=["KYC Verification (Phone)"])

router.include_router(force_kyc_refresh_router)

# Compatibility with main.py pattern: `from app.api.routes.kyc.phone import router; app.include_router(router.router)`
router.router = router

__all__ = ["router", "force_kyc_refresh_router"]
