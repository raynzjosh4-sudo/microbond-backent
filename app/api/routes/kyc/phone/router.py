from fastapi import APIRouter
from .force_kyc_refresh import router as force_kyc_refresh_router

router = APIRouter(prefix="/api/v1/kyc/phone", tags=["KYC Verification (Phone)"])

router.include_router(force_kyc_refresh_router)
