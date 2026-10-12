from fastapi import APIRouter
from .mtn.router import router as mtn_router
from .airtel.router import router as airtel_router
from .deposit import router as deposit_execution_router

router = APIRouter(prefix="/api/v1/mobile-money")

router.include_router(mtn_router)
router.include_router(airtel_router)
router.include_router(deposit_execution_router)


