from fastapi import APIRouter
from .initiate_wallet_withdrawal import (
    router as initiate_router,
    initiate_wallet_withdrawal,
)

router = APIRouter(prefix="/withdraw", tags=["Mobile Money Disbursements"])
router.include_router(initiate_router)

__all__ = ["router", "initiate_wallet_withdrawal"]
