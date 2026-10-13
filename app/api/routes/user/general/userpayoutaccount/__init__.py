from fastapi import APIRouter
from .add_payout_destination import router as add_router
from .list_payout_destinations import router as list_router
from .delete_payout_destination import router as delete_router

router = APIRouter(
    prefix="/api/v1/users/me/payout-destinations",
    tags=["User Payout Destinations"],
)

router.include_router(add_router)
router.include_router(list_router)
router.include_router(delete_router)

__all__ = ["router", "add_router", "list_router", "delete_router"]
