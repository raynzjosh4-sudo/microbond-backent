from fastapi import APIRouter
from .general.profile_status import router as profile_router
from .general.userpayoutaccount.router import router as payout_destination_router
from .general.userpaymentmethod.router import router as payment_method_router

router = APIRouter()

router.include_router(profile_router)
router.include_router(payout_destination_router)
router.include_router(payment_method_router)
