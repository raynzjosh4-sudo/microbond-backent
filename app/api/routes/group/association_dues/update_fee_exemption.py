import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.investment_association import AssociationDuesExemption
from .schemas import UpdateDuesExemptionRequest
from .helpers import now_ms, require_admin

logger = logging.getLogger(__name__)

router = APIRouter()

@router.patch("/{group_id}/exemptions/{exemption_id}", summary="Admin: Update or modify a fee exemption")
def update_fee_exemption(
    group_id: str,
    exemption_id: str,
    request: UpdateDuesExemptionRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Admin updates an existing fee exemption (change duration, notes, discount percentage, or status).
    """
    require_admin(group_id, current_user, session)
    try:
        ex_uuid = uuid.UUID(exemption_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid exemption_id format.")

    exemption = session.exec(
        select(AssociationDuesExemption).where(
            AssociationDuesExemption.id == ex_uuid,
            AssociationDuesExemption.group_id == group_id
        )
    ).first()
    if not exemption:
        raise HTTPException(status_code=404, detail="Fee exemption not found.")

    update_dict = request.dict(exclude_unset=True)
    for field, val in update_dict.items():
        if hasattr(exemption, field) and val is not None:
            setattr(exemption, field, val)

    exemption.updated_at = now_ms()
    session.add(exemption)

    try:
        session.commit()
        session.refresh(exemption)
    except Exception as e:
        session.rollback()
        logger.exception(f"Error updating fee exemption: {e}")
        raise HTTPException(status_code=500, detail="Database error updating fee exemption.")

    return {
        "status": "success",
        "message": "Fee exemption updated successfully.",
        "data": exemption.model_dump(mode="json")
    }
