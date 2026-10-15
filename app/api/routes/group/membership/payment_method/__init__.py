from fastapi import APIRouter
from .set_group_payment_method import router as set_group_payment_method_router, set_group_payment_method
from .get_group_payment_method import router as get_group_payment_method_router, get_group_payment_method
from .helpers import mask_account_number

router = APIRouter(prefix="/api/v1/groups", tags=["Group Membership"])
router.include_router(set_group_payment_method_router)
router.include_router(get_group_payment_method_router)
router.router = router

__all__ = [
    "router",
    "set_group_payment_method",
    "get_group_payment_method",
    "mask_account_number",
]
