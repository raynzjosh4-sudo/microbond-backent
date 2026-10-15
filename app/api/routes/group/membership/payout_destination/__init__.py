from fastapi import APIRouter
from .get_my_payout_destination import router as get_my_payout_destination_router, get_my_payout_destination
from .set_my_payout_destination import router as set_my_payout_destination_router, set_my_payout_destination
from .helpers import mask_number, format_destination_response

router = APIRouter(prefix="/api/v1/groups", tags=["Group Membership Payouts"])
router.include_router(get_my_payout_destination_router)
router.include_router(set_my_payout_destination_router)
router.router = router

__all__ = [
    "router",
    "get_my_payout_destination",
    "set_my_payout_destination",
    "mask_number",
    "format_destination_response",
]
