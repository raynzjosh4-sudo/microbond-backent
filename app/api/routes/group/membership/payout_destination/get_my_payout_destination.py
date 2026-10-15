from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.user.userpayoutaccount.payout_destination import UserPayoutDestination
from app.models.group.group import GroupMembership
from .helpers import mask_number, format_destination_response

router = APIRouter()

@router.get("/{group_id}/membership/me/payout-destination", summary="Get My Payout Destination for Group")
def get_my_payout_destination(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # 1. Check group membership
    membership = session.query(GroupMembership).filter(
        GroupMembership.group_id == group_id,
        GroupMembership.user_id == current_user.id
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You are not a member of this group."
        )

    # 2. If the user explicitly chose a destination for THIS group
    if membership.payout_destination_id:
        destination = session.query(UserPayoutDestination).filter(
            UserPayoutDestination.id == membership.payout_destination_id,
            UserPayoutDestination.user_id == current_user.id
        ).first()
        
        if destination:
            return format_destination_response(destination, source="GROUP_SPECIFIC")

    # 3. If no group-specific destination, look for the user's global default
    default_destination = session.query(UserPayoutDestination).filter(
        UserPayoutDestination.user_id == current_user.id,
        UserPayoutDestination.is_default == True
    ).first()
    
    if default_destination:
        return format_destination_response(default_destination, source="GLOBAL_DEFAULT")

    # 4. Fallback: Use the user's registered phone number as Mobile Money
    return {
        "status": "success",
        "source": "FALLBACK_PHONE_NUMBER",
        "data": {
            "provider_name": "Mobile Money",
            "account_number": current_user.phone_number,
            "account_name": current_user.full_name or "User",
            "masked_number": mask_number(current_user.phone_number)
        }
    }
