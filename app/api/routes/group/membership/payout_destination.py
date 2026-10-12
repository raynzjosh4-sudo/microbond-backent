from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from sqlmodel import Session

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.user.userpayoutaccount.payout_destination import UserPayoutDestination
from app.models.group.group import GroupMembership

router = APIRouter(prefix="/api/v1/groups", tags=["Group Membership Payouts"])

class SetPayoutDestinationRequest(BaseModel):
    payout_destination_id: Optional[str] = None

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
            return _format_destination_response(destination, source="GROUP_SPECIFIC")

    # 3. If no group-specific destination, look for the user's global default
    default_destination = session.query(UserPayoutDestination).filter(
        UserPayoutDestination.user_id == current_user.id,
        UserPayoutDestination.is_default == True
    ).first()
    
    if default_destination:
        return _format_destination_response(default_destination, source="GLOBAL_DEFAULT")

    # 4. Fallback: Use the user's registered phone number as Mobile Money
    return {
        "status": "success",
        "source": "FALLBACK_PHONE_NUMBER",
        "data": {
            "provider_name": "Mobile Money",
            "account_number": current_user.phone_number,
            "account_name": current_user.full_name or "User",
            "masked_number": _mask_number(current_user.phone_number)
        }
    }

@router.put("/{group_id}/membership/me/payout-destination", summary="Set My Payout Destination for Group")
def set_my_payout_destination(
    group_id: str,
    request: SetPayoutDestinationRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    membership = session.query(GroupMembership).filter(
        GroupMembership.group_id == group_id,
        GroupMembership.user_id == current_user.id
    ).first()

    if not membership:
        raise HTTPException(status_code=404, detail="Membership not found.")

    if request.payout_destination_id:
        # Verify the destination actually belongs to the user
        valid_dest = session.query(UserPayoutDestination).filter(
            UserPayoutDestination.id == request.payout_destination_id,
            UserPayoutDestination.user_id == current_user.id
        ).first()
        
        if not valid_dest:
            raise HTTPException(status_code=400, detail="Invalid payout destination.")

    membership.payout_destination_id = request.payout_destination_id
    session.commit()
    
    return {"status": "success", "message": "Group payout destination updated."}


def _mask_number(number: str) -> str:
    """Masks all but the last 4 digits (e.g., **** 1234)"""
    if not number or len(number) < 4:
        return "****"
    return f"**** {number[-4:]}"

def _format_destination_response(dest: UserPayoutDestination, source: str) -> dict:
    return {
        "status": "success",
        "source": source,
        "data": {
            "id": dest.id,
            "provider_name": dest.provider_name,
            "account_number": dest.account_number,
            "verified_name": dest.verified_name,
            "account_name": dest.verified_name,  # Backward compatibility for mobile client
            "account_type": dest.account_type,
            "is_verified": dest.is_verified,
            "verification_type": dest.verification_type,
            "masked_number": _mask_number(dest.account_number)
        }
    }

