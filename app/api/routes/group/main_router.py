from fastapi import APIRouter
from .rotating.router import router as rotating_router
from .target_savings.router import router as target_savings_router
from .settings.router import router as settings_router

router = APIRouter()

router.include_router(rotating_router)
router.include_router(target_savings_router)
router.include_router(settings_router)
