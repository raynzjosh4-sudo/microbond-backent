from fastapi import APIRouter
from .add_payment_method import router as add_router
from .list_payment_methods import router as list_router
from .delete_payment_method import router as delete_router

router = APIRouter(
    prefix="/api/v1/users/me/payment-methods", tags=["User Payment Methods"]
)

router.include_router(add_router)
router.include_router(list_router)
router.include_router(delete_router)

__all__ = ["router", "add_router", "list_router", "delete_router"]
