from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.user.userpayoutaccount.payout_destination import UserPayoutDestination
from app.models.user.userpayoutaccount.schema.payout_destination_schema import CreatePayoutDestinationRequest, PayoutDestinationResponse

router = APIRouter()

def _mask_number(number: str) -> str:
    if not number or len(number) < 4:
        return "****"
    return f"**** {number[-4:]}"

@router.post("/", response_model=PayoutDestinationResponse, summary="Add a new payout destination")
def add_payout_destination(
    request: CreatePayoutDestinationRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # If this is set as default, remove default from others
    if request.is_default:
        session.query(UserPayoutDestination).filter(
            UserPayoutDestination.user_id == current_user.id
        ).update({"is_default": False})

    new_dest = UserPayoutDestination(
        user_id=current_user.id,
        provider_name=request.provider_name,
        account_number=request.account_number,
        account_name=request.account_name,
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
        account_name=new_dest.account_name,
        is_default=new_dest.is_default,
        masked_number=_mask_number(new_dest.account_number)
    )
