from fastapi import APIRouter
from .general.profile import router as profile_router
from .general.userpayoutaccount import router as payout_destination_router
from .general.userpaymentmethod import router as payment_method_router
from .general.email import router as email_router
from .general.avatar import router as avatar_router
from .general.presence import router as presence_router
from .general.account_deletion import router as account_deletion_router
from .general.fcm_token import router as fcm_token_router
from .general.contacts import router as contacts_router
from .general.privacy import router as privacy_router

router = APIRouter()
router.include_router(profile_router)
router.include_router(avatar_router)
router.include_router(presence_router)
router.include_router(account_deletion_router)
router.include_router(payout_destination_router)
router.include_router(payment_method_router)
router.include_router(email_router)
router.include_router(fcm_token_router)
router.include_router(contacts_router)
router.include_router(privacy_router)
router.router = router

__all__ = ["router"]

