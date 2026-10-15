from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.user.userpayoutaccount.payout_destination import UserPayoutDestination
from app.models.group.group import GroupMembership
from .schemas import SetPayoutDestinationRequest

router = APIRouter()

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
