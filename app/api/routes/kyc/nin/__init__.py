from fastapi import APIRouter
from .sumsub import router as sumsub_router
from .prembly import router as prembly_router
from ..decision import router as decision_router

router = APIRouter(prefix="/api/v1/kyc/nin")

router.include_router(sumsub_router)
router.include_router(prembly_router)
router.include_router(decision_router)

__all__ = ["router", "sumsub_router", "prembly_router", "decision_router"]
