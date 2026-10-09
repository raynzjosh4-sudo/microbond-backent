from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.user.userpayoutaccount.payout_destination import UserPayoutDestination

router = APIRouter()

@router.delete("/{destination_id}", summary="Delete a payout destination")
def delete_payout_destination(
    destination_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    dest = session.query(UserPayoutDestination).filter(
        UserPayoutDestination.id == destination_id,
        UserPayoutDestination.user_id == current_user.id
    ).first()
    
    if not dest:
        raise HTTPException(status_code=404, detail="Destination not found.")
        
    session.delete(dest)
    session.commit()
    return {"status": "success", "message": "Payout destination deleted."}
