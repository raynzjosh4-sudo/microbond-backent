from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.core.security import verify_pin
from app.models.user.userpayoutaccount.payout_destination import UserPayoutDestination
from app.models.user.userpayoutaccount.schema.payout_destination_schema import CreatePayoutDestinationRequest, PayoutDestinationResponse
from app.services.finance.payout_verification_service import PayoutAccountVerificationService

router = APIRouter()

def _mask_number(number: str) -> str:
    if not number or len(number) < 4:
        return "****"
    return f"**** {number[-4:]}"

@router.post("/", response_model=PayoutDestinationResponse, summary="Add a new payout destination")
async def add_payout_destination(
    request: CreatePayoutDestinationRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # Step-Up PIN validation if user has an active PIN
    if current_user.hashed_pin:
        pin_to_check = request.app_pin if request.app_pin and request.app_pin.strip().lower() != "string" else None
        if not pin_to_check:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="App PIN is required to add a payout destination. Please enter your valid 4-digit PIN."
            )
        if not verify_pin(pin_to_check, current_user.hashed_pin):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect App PIN."
            )

    # Clean dummy Swagger placeholders
    clean_bank_code = request.bank_code if request.bank_code and request.bank_code.strip().lower() not in ["string", ""] else None
    
    # Auto-detect account_type ('MOBILE_MONEY' or 'BANK_ACCOUNT') if omitted
    resolved_type = PayoutAccountVerificationService.resolve_account_type(
        provider_name=request.provider_name,
        account_number=request.account_number,
        account_type=request.account_type
    )

    # Verify destination using external authority (MTN / Airtel / Prembly)
    verification = await PayoutAccountVerificationService.verify(
        provider_name=request.provider_name,
        account_type=resolved_type,
        account_number=request.account_number,
        bank_code=clean_bank_code,
    )

    # If this is set as default, remove default from others
    if request.is_default:
        session.query(UserPayoutDestination).filter(
            UserPayoutDestination.user_id == current_user.id
        ).update({"is_default": False})

    new_dest = UserPayoutDestination(
        user_id=current_user.id,
        provider_name=request.provider_name,
        account_number=request.account_number,
        account_name=verification.verified_name,
        account_type=resolved_type,
        is_verified=verification.is_verified,
        verified_name=verification.verified_name,
        verification_type=verification.verification_type,
        is_default=request.is_default
    )
    
    session.add(new_dest)
    session.commit()
    session.refresh(new_dest)
    
    # If it's the first destination they ever added, make it default automatically
    if not request.is_default:
        count = session.query(UserPayoutDestination).filter(
            UserPayoutDestination.user_id == current_user.id
        ).count()
        if count == 1:
            new_dest.is_default = True
            session.commit()
            session.refresh(new_dest)
            
    return PayoutDestinationResponse(
        id=new_dest.id,
        provider_name=new_dest.provider_name,
        account_number=new_dest.account_number,
        account_name=new_dest.account_name or new_dest.verified_name,
        account_type=new_dest.account_type,
        verified_name=new_dest.verified_name,
        is_verified=new_dest.is_verified,
        is_default=new_dest.is_default,
        masked_number=_mask_number(new_dest.account_number),
        verification_type=new_dest.verification_type
    )
