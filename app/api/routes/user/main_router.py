from fastapi import APIRouter
from .general.profile_status import router as profile_router
from .general.userpayoutaccount.router import router as payout_destination_router
from .general.userpaymentmethod.router import router as payment_method_router
from .general.email import router as email_router
from .general.update_name import router as update_name_router
from .general.avatar import router as avatar_router
from .general.presence import router as presence_router
from .general.account_deletion import router as account_deletion_router
from .general.fcm_token import router as fcm_token_router

router = APIRouter()

router.include_router(profile_router)
router.include_router(update_name_router)
router.include_router(avatar_router)
router.include_router(presence_router)
router.include_router(account_deletion_router)
router.include_router(payout_destination_router)
router.include_router(payment_method_router)
router.include_router(email_router)
router.include_router(fcm_token_router)
