from fastapi import APIRouter
from .logout import router as logout_endpoint_router, logout_user

router = APIRouter(tags=["Authentication"])

# Support standard versioned path: /api/v1/auth/logout
router.include_router(logout_endpoint_router, prefix="/api/v1/auth")

# Support unversioned aliases: /auth/logout and /logout
router.include_router(logout_endpoint_router, prefix="/auth")
router.include_router(logout_endpoint_router)

__all__ = ["router", "logout_user"]
