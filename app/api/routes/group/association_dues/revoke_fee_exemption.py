import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.investment_association import AssociationDuesExemption
from .helpers import require_admin

logger = logging.getLogger(__name__)

router = APIRouter()

@router.delete("/{group_id}/exemptions/{exemption_id}", summary="Admin: Revoke / delete a fee exemption")
def revoke_fee_exemption(
    group_id: str,
    exemption_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Revokes and deletes an exemption, returning the member to standard dues billing.
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

    session.delete(exemption)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error deleting fee exemption: {e}")
        raise HTTPException(status_code=500, detail="Database error deleting fee exemption.")

    return {
        "status": "success",
        "message": "Fee exemption revoked successfully."
    }
