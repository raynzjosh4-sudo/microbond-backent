from fastapi import APIRouter
from .verify_typed_nin import router as verify_typed_nin_router
from .verify_scanned_id import router as verify_scanned_id_router

router = APIRouter(prefix="/prembly", tags=["KYC Verification (Prembly)"])

router.include_router(verify_typed_nin_router)
router.include_router(verify_scanned_id_router)
