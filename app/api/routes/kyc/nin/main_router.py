from fastapi import APIRouter
from .sumsub.router import router as sumsub_router
from .prembly.router import router as prembly_router
from ..decision import router as decision_router

router = APIRouter(prefix="/api/v1/kyc/nin")

router.include_router(sumsub_router)
router.include_router(prembly_router)
router.include_router(decision_router)
