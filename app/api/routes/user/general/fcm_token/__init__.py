from fastapi import APIRouter
from .register_fcm_token import router as register_router, register_fcm_token
from .deregister_fcm_token import router as deregister_router, deregister_fcm_token

router = APIRouter(prefix="/api/v1/users", tags=["Push Notifications"])
router.include_router(register_router)
router.include_router(deregister_router)

__all__ = ["router", "register_fcm_token", "deregister_fcm_token"]
