from fastapi import APIRouter
from .verify_typed_nin import router as verify_typed_nin_router
from .verify_scanned_id import router as verify_scanned_id_router

router = APIRouter(prefix="/sumsub", tags=["KYC Verification (Sumsub)"])

router.include_router(verify_typed_nin_router)
router.include_router(verify_scanned_id_router)

__all__ = ["router", "verify_typed_nin_router", "verify_scanned_id_router"]
