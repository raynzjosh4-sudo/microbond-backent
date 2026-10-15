import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.group import GroupMembership
from app.models.user.user import User
from app.models.group.investment_association import AssociationDuesExemption
from .schemas import CreateDuesExemptionRequest
from .helpers import now_ms as _now_ms, require_admin

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/{group_id}/exemptions", summary="Admin: Grant temporary or permanent dues exemption to a member")
def grant_fee_exemption(
    group_id: str,
    request: CreateDuesExemptionRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Grants a dues fee exemption to a member (e.g. students, hardship, elders, honorary members).
    Can be a 100% full waiver or partial discount (discount_percentage).
    """
    require_admin(group_id, current_user, session)
    now_ms = _now_ms()

    # Verify target user exists and is member of group
    try:
        target_uuid = uuid.UUID(request.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format. Must be a valid UUID.")

    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == target_uuid,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Target user is not an active member of this association.")

    # Check if there is already an active exemption
    existing = session.exec(
        select(AssociationDuesExemption).where(
            AssociationDuesExemption.group_id == group_id,
            AssociationDuesExemption.user_id == target_uuid,
            AssociationDuesExemption.is_active == True
        )
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Member already has an active fee exemption. Please update or revoke it first.")

    start_date = request.start_date if request.start_date else now_ms
    if request.exemption_type == "TEMPORARY" and not request.end_date:
        raise HTTPException(status_code=400, detail="Temporary exemptions must include an end_date.")

    exemption = AssociationDuesExemption(
        group_id=group_id,
        user_id=target_uuid,
        exemption_type=request.exemption_type,
        reason=request.reason,
        notes=request.notes,
        discount_percentage=request.discount_percentage,
        start_date=start_date,
        end_date=request.end_date,
        is_active=True,
        approved_by=current_user.id,
        created_at=now_ms,
        updated_at=now_ms
    )
    session.add(exemption)

    try:
        session.commit()
        session.refresh(exemption)
    except Exception as e:
        session.rollback()
        logger.exception(f"Error creating fee exemption: {e}")
        raise HTTPException(status_code=500, detail="Database error creating fee exemption.")

    return {
        "status": "success",
        "message": "Fee exemption granted successfully.",
        "data": exemption.model_dump(mode="json")
    }
