from fastapi import APIRouter
from .africastalking.router import router as at_router
from .firebase.router import router as firebase_router

router = APIRouter()

router.include_router(at_router)
router.include_router(firebase_router)
