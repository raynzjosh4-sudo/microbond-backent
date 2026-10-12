from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import require_telecom_kyc_guard
from app.models.user.user import User

from app.core.security import verify_pin

router = APIRouter(prefix="/withdraw", tags=["Mobile Money Disbursements"])

class InitiateWithdrawalRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Amount in UGX (Integer)")
    destination_msisdn: str = Field(..., description="Phone number to receive funds")
    app_pin: str = Field(..., min_length=4, max_length=8, description="User App PIN for transaction confirmation")

@router.post(
    "/initiate",
    summary="High-Security Wallet Withdrawal",
    description="Protected by live Telecom KYC & SIM-Swap Tripwire Guard plus Server-Side App PIN verification."
)
async def initiate_wallet_withdrawal(
    payload: InitiateWithdrawalRequest,
    current_user: User = Depends(require_telecom_kyc_guard),
    session: Session = Depends(get_session)
):
    """
    If the line was swapped in the last 72 hours, or if the user is in a 
    Security Cooldown / KYC Re-verification state, this endpoint aborts with HTTP 403.
    Requires valid App PIN for step-up transaction execution.
    """
    if not current_user.hashed_pin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must set up an App PIN before performing withdrawals."
        )

    if not verify_pin(payload.app_pin, current_user.hashed_pin):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect App PIN. Withdrawal aborted."
        )

    return {
        "status": "success",
        "message": f"Withdrawal of {payload.amount} UGX to {payload.destination_msisdn} authorized.",
        "account_id": str(current_user.id),
        "telecom_kyc_verified": True
    }
