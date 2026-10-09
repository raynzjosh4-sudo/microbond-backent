from fastapi import APIRouter
from .verify_firebase_token import router as verify_firebase_token_router

# Specifically scoped for OTP Authentication
router = APIRouter(prefix="/api/v1/kyc/phone/firebase", tags=["KYC Verification (Phone - Firebase)"])

router.include_router(verify_firebase_token_router)
