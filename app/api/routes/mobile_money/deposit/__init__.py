from fastapi import APIRouter
from .execute_mobile_money_deposit import (
    router as execute_router,
    execute_mobile_money_deposit,
)

router = APIRouter(prefix="/deposit", tags=["Mobile Money Deposit Execution"])
router.include_router(execute_router)

__all__ = ["router", "execute_mobile_money_deposit"]
