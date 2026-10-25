from fastapi import APIRouter
from .request_turn_swap import router as request_turn_swap_router, request_turn_swap
from .accept_turn_swap import router as accept_turn_swap_router, accept_turn_swap
from .reject_turn_swap import router as reject_turn_swap_router, reject_turn_swap
from .admin_review_swap import router as admin_review_swap_router, admin_review_turn_swap

router = APIRouter(prefix="/api/v1/groups", tags=["Group Payout Turn Swapping"])
router.include_router(request_turn_swap_router)
router.include_router(accept_turn_swap_router)
router.include_router(reject_turn_swap_router)
router.include_router(admin_review_swap_router)
router.router = router

__all__ = [
    "router",
    "request_turn_swap",
    "accept_turn_swap",
    "reject_turn_swap",
    "admin_review_turn_swap",
]

