from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Dict, Optional, List
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
    user_positions: Optional[Dict[str, int]] = Field(
        default=None, 
        description="Map of user_id to position number (1-based)"
    )
    # Alternatively, a simple ordered list of user IDs from 1st to last
    ordered_member_ids: Optional[List[str]] = Field(
        default=None, 
        description="Ordered list of user IDs from position 1 to N"
    )
    # Optional strategy update (e.g. 'Admin-Assigned')
    strategy: Optional[str] = Field(
        default=None,
        description="Optionally update payout_order_strategy at the same time"
    )

@router.get("/{group_id}/rotating/admin-payout-order", summary="Get Payout Order Roster")
@router.get("/{group_id}/admin-payout-order", summary="Get Payout Order Roster (Alias)")
def get_payout_order_roster(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    rotating_details = session.query(RotatingGroupDetails).filter_by(group_id=group_id).first()
    if not rotating_details:
        raise HTTPException(status_code=404, detail="This is not a rotating savings group.")

    members = session.query(GroupMembership).filter_by(group_id=group_id, status="ACTIVE").all()
    sorted_members = sorted(members, key=lambda m: (m.payout_position or 999))
    
    roster = []
    for m in sorted_members:
        user = session.query(User).filter_by(id=m.user_id).first()
        roster.append({
            "user_id": str(m.user_id),
            "name": user.full_name if user else "Member",
            "phone_number": user.phone_number if user else "",
            "role": m.role,
            "payout_position": m.payout_position
        })

    return {
        "status": "success",
        "data": {
            "group_id": group_id,
            "strategy": rotating_details.payout_order_strategy,
            "is_locked": rotating_details.is_payout_order_locked,
            "roster": roster
        }
    }


@router.patch("/{group_id}/rotating/admin-payout-order", summary="Admin: Assign Payout Order")
@router.patch("/{group_id}/admin-payout-order", summary="Admin: Assign Payout Order (Alias)")
@router.post("/{group_id}/rotating/admin-payout-order", summary="Admin: Assign Payout Order (POST Alias)")
@router.post("/{group_id}/admin-payout-order", summary="Admin: Assign Payout Order (POST Alias)")
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

    # Auto-switch strategy to Admin-Assigned if not already set
    if request.strategy:
        strat_norm = request.strategy.strip()
        strat_upper = strat_norm.upper().replace("-", "_").replace(" ", "_")
        if strat_upper in ["ADMIN", "ADMIN_ASSIGNED"]:
            rotating_details.payout_order_strategy = "Admin-Assigned"
        else:
            rotating_details.payout_order_strategy = strat_norm
    else:
        strat_clean = (rotating_details.payout_order_strategy or "").replace("-", " ").strip().lower()
        if strat_clean != "admin assigned":
            rotating_details.payout_order_strategy = "Admin-Assigned"
            session.add(rotating_details)


    # 3. Resolve user positions from either map or ordered list
    positions_map: Dict[str, int] = {}
    if request.ordered_member_ids is not None:
        for idx, uid in enumerate(request.ordered_member_ids, start=1):
            positions_map[str(uid)] = idx
    elif request.user_positions is not None:
        for uid, pos in request.user_positions.items():
            positions_map[str(uid)] = pos
    else:
        raise HTTPException(
            status_code=400,
            detail="Must provide either 'ordered_member_ids' (list) or 'user_positions' (map)."
        )

    # 4. Fetch all members
    members = session.query(GroupMembership).filter_by(group_id=group_id).all()
    member_dict = {str(m.user_id): m for m in members}

    # 5. Validate all positions and assign
    assigned_positions = set()
    for uid_str, pos in positions_map.items():
        if uid_str not in member_dict:
            raise HTTPException(status_code=400, detail=f"User {uid_str} is not a member of this group.")
            
        if pos <= 0:
            raise HTTPException(status_code=400, detail="Positions must be 1 or greater.")
            
        if pos in assigned_positions:
            raise HTTPException(status_code=400, detail=f"Duplicate position {pos} detected. Each member must have a unique turn.")
            
        assigned_positions.add(pos)
        
        # Update the database model
        member_dict[uid_str].payout_position = pos

    session.commit()
    
    return {"status": "success", "message": "Payout positions successfully assigned."}
