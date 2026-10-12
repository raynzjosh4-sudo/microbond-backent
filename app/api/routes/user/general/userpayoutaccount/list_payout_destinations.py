from fastapi import APIRouter, Depends
from typing import List
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.user.userpayoutaccount.payout_destination import UserPayoutDestination
from app.models.user.userpayoutaccount.schema.payout_destination_schema import PayoutDestinationResponse

router = APIRouter()

def _mask_number(number: str) -> str:
    if not number or len(number) < 4:
        return "****"
    return f"**** {number[-4:]}"

@router.get("/", response_model=List[PayoutDestinationResponse], summary="List my payout destinations")
def list_my_payout_destinations(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    destinations = session.query(UserPayoutDestination).filter(
        UserPayoutDestination.user_id == current_user.id
    ).all()
    
    results = []
    for dest in destinations:
        results.append(PayoutDestinationResponse(
            id=dest.id,
            provider_name=dest.provider_name,
            account_number=dest.account_number,
            account_name=dest.account_name or dest.verified_name,
            account_type=dest.account_type,
            verified_name=dest.verified_name,
            is_verified=dest.is_verified,
            is_default=dest.is_default,
            masked_number=_mask_number(dest.account_number),
            verification_type=dest.verification_type,
        ))
    return results
