from fastapi import APIRouter
from .africastalking import router as at_router
from .firebase import router as firebase_router

router = APIRouter()

router.include_router(at_router)
router.include_router(firebase_router)

__all__ = ["router"]
