from fastapi import APIRouter
from .set_pin import router as set_pin_router
from .verify_pin import router as verify_pin_router
from .change_pin import router as change_pin_router
from .forgot_pin import router as forgot_pin_router

router = APIRouter()
router.include_router(set_pin_router)
router.include_router(verify_pin_router)
router.include_router(change_pin_router)
router.include_router(forgot_pin_router)

__all__ = [
    "router",
    "set_pin_router",
    "verify_pin_router",
    "change_pin_router",
    "forgot_pin_router",
]
