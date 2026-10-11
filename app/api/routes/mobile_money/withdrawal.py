from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import require_telecom_kyc_guard
from app.models.user.user import User

router = APIRouter(prefix="/withdraw", tags=["Mobile Money Disbursements"])

class InitiateWithdrawalRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Amount in UGX (Integer)")
    destination_msisdn: str = Field(..., description="Phone number to receive funds")

@router.post(
    "/initiate",
    summary="High-Security Wallet Withdrawal",
    description="Protected by live Telecom KYC & SIM-Swap Tripwire Guard."
)
async def initiate_wallet_withdrawal(
    payload: InitiateWithdrawalRequest,
    current_user: User = Depends(require_telecom_kyc_guard),
    session: Session = Depends(get_session)
):
    """
    If the line was swapped in the last 72 hours, or if the user is in a 
    Security Cooldown / KYC Re-verification state, this endpoint aborts with HTTP 403.
    """
    return {
        "status": "success",
        "message": f"Withdrawal of {payload.amount} UGX to {payload.destination_msisdn} authorized.",
        "account_id": str(current_user.id),
        "telecom_kyc_verified": True
    }
