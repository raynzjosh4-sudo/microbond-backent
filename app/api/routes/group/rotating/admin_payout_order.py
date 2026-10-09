from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict
from sqlmodel import Session
from uuid import UUID

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.rotating import RotatingGroupDetails

router = APIRouter(prefix="/api/v1/groups", tags=["Rotating Group"])

class AdminPayoutOrderRequest(BaseModel):
    # Mapping of user_id to their desired payout position (1-based index)
    user_positions: Dict[UUID, int]

@router.patch("/{group_id}/rotating/admin-payout-order", summary="Admin: Assign Payout Order")
def assign_payout_order(
    group_id: str,
    request: AdminPayoutOrderRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # 1. Verify caller is an Admin in this group
    admin_membership = session.query(GroupMembership).filter_by(
        group_id=group_id, user_id=current_user.id, role="ADMIN"
    ).first()

    if not admin_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Only group admins can assign payout positions."
        )

    # 2. Check Rotating Settings
    rotating_details = session.query(RotatingGroupDetails).filter_by(group_id=group_id).first()
    if not rotating_details:
        raise HTTPException(status_code=404, detail="This is not a rotating savings group.")

    if rotating_details.is_payout_order_locked:
        raise HTTPException(status_code=400, detail="The payout order is locked and cannot be changed.")

    if rotating_details.payout_order_strategy != "Admin-Assigned":
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot manually assign positions. The strategy is set to: {rotating_details.payout_order_strategy}"
        )

    # 3. Fetch all members
    members = session.query(GroupMembership).filter_by(group_id=group_id).all()
    member_dict = {m.user_id: m for m in members}

    # 4. Validate all positions and assign
    assigned_positions = set()
    for user_id, pos in request.user_positions.items():
        if user_id not in member_dict:
            raise HTTPException(status_code=400, detail=f"User {user_id} is not a member of this group.")
            
        if pos <= 0:
            raise HTTPException(status_code=400, detail="Positions must be 1 or greater.")
            
        if pos in assigned_positions:
            raise HTTPException(status_code=400, detail=f"Duplicate position {pos} detected. Each member must have a unique turn.")
            
        assigned_positions.add(pos)
        
        # Update the database model
        member_dict[user_id].payout_position = pos

    session.commit()
    
    return {"status": "success", "message": "Payout positions successfully assigned."}
