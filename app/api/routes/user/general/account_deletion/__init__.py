from fastapi import APIRouter
from .export_user_data import router as export_router, export_user_data
from .delete_user_account import router as delete_router, delete_user_account

router = APIRouter(prefix="/api/v1/users", tags=["Account Management & GDPR"])
router.include_router(export_router)
router.include_router(delete_router)

__all__ = ["router", "export_user_data", "delete_user_account"]
