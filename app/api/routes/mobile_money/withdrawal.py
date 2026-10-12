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
    summary="[Deprecated] Manual Wallet Withdrawal",
    description="Deprecated: Microbond automatically disburses funds directly to members' chosen payout accounts via the background payout worker on cycle maturity.",
    deprecated=True
)
async def initiate_wallet_withdrawal(
    payload: InitiateWithdrawalRequest,
    current_user: User = Depends(require_telecom_kyc_guard),
    session: Session = Depends(get_session)
):
    """
    Microbond does not require manual wallet withdrawals.
    Group funds are automatically swept and disbursed to the member's chosen payout
    account (MTN MoMo, Airtel Money, or Bank) by the background disbursement worker.
    """
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Manual wallet withdrawals are not required. Group funds are automatically disbursed to your chosen payout destination when your cycle matures."
    )

