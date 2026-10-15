from fastapi import APIRouter
from .start_auction import router as start_auction_router, start_auction
from .get_active_auction import router as get_active_auction_router, get_active_auction
from .get_auction_details import router as get_auction_details_router, get_auction_details
from .submit_bid import router as submit_bid_router, submit_bid

router = APIRouter(tags=["Rotating Auctions"])
router.include_router(start_auction_router)
router.include_router(get_active_auction_router)
router.include_router(get_auction_details_router)
router.include_router(submit_bid_router)
router.router = router

__all__ = [
    "router",
    "start_auction",
    "get_active_auction",
    "get_auction_details",
    "submit_bid",
]
