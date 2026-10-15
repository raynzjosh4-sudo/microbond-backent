from fastapi import APIRouter
from .create_bill_split_group import router as create_bill_split_group_router, create_bill_split_group
from .get_bill_split_dashboard import router as get_bill_split_dashboard_router, get_bill_split_dashboard
from .get_bill_split_settings import router as get_bill_split_settings_router, get_bill_split_settings
from .update_bill_split_settings import router as update_bill_split_settings_router, update_bill_split_settings
from .pay_bill_share import router as pay_bill_share_router, pay_bill_share
from .mark_bill_settled import router as mark_bill_settled_router, mark_bill_settled
from .remind_defaulters import router as remind_defaulters_router, remind_defaulters

router = APIRouter(prefix="/api/v1/groups/bill-split", tags=["Bill Split Groups"])
router.include_router(create_bill_split_group_router)
router.include_router(get_bill_split_dashboard_router)
router.include_router(get_bill_split_settings_router)
router.include_router(update_bill_split_settings_router)
router.include_router(pay_bill_share_router)
router.include_router(mark_bill_settled_router)
router.include_router(remind_defaulters_router)
router.router = router

__all__ = [
    "router",
    "create_bill_split_group",
    "get_bill_split_dashboard",
    "get_bill_split_settings",
    "update_bill_split_settings",
    "pay_bill_share",
    "mark_bill_settled",
    "remind_defaulters",
]
