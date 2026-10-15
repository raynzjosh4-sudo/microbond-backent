from fastapi import APIRouter
from .inbound_confirmation import router as inbound_confirmation_router

router = APIRouter(prefix="/api/v1/payments", tags=["External Payments"])

router.include_router(inbound_confirmation_router)

__all__ = ["router", "inbound_confirmation_router"]
