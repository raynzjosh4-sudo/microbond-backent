from fastapi import APIRouter
from .nin import router as nin_router
from .phone import router as phone_router

router = APIRouter()
router.include_router(nin_router)
router.include_router(phone_router)

__all__ = ["router", "nin_router", "phone_router"]
