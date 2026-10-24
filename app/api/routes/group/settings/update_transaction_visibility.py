from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.settings import GroupVisibilitySettings

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])

class UpdateTransactionVisibilityRequest(BaseModel):
    vis_broadcast_individual_deposit_receipts: Optional[bool] = None
    vis_broadcast_individual_dues_receipts: Optional[bool] = None
    vis_broadcast_individual_loan_receipts: Optional[bool] = None
    vis_announce_payout_updates: Optional[bool] = None
    vis_announce_dues_adjustment_updates: Optional[bool] = None
    vis_announce_loan_disbursement_updates: Optional[bool] = None
    vis_show_transfer_receipts: Optional[bool] = None
    vis_announce_admin_transactions: Optional[bool] = None

@router.patch("/{group_id}/settings/transaction-visibility", summary="Admin: Update Transaction Messages Visibility")
@router.patch("/{group_id}/settings/contribution-visibility", summary="Admin: Update Contribution Messages Visibility")
@router.patch("/{group_id}/settings/loan-messages-visibility", summary="Admin: Update Loan & Investment Messages Visibility")
def update_transaction_visibility_settings(
    group_id: str, 
    request: UpdateTransactionVisibilityRequest, 
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    admin_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.role == "ADMIN"
        )
    ).first()
    
    if not admin_membership:
        raise HTTPException(status_code=403, detail="Only the Group Admin can update visibility settings.")

    settings = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()
    
    if not settings:
        raise HTTPException(status_code=404, detail="Visibility settings not found.")

    if request.vis_broadcast_individual_deposit_receipts is not None:
        settings.vis_broadcast_individual_deposit_receipts = request.vis_broadcast_individual_deposit_receipts
    if request.vis_broadcast_individual_dues_receipts is not None:
        settings.vis_broadcast_individual_dues_receipts = request.vis_broadcast_individual_dues_receipts
    if request.vis_broadcast_individual_loan_receipts is not None:
        settings.vis_broadcast_individual_loan_receipts = request.vis_broadcast_individual_loan_receipts
    if request.vis_announce_payout_updates is not None:
        settings.vis_announce_payout_updates = request.vis_announce_payout_updates
    if request.vis_announce_dues_adjustment_updates is not None:
        settings.vis_announce_dues_adjustment_updates = request.vis_announce_dues_adjustment_updates
    if request.vis_announce_loan_disbursement_updates is not None:
        settings.vis_announce_loan_disbursement_updates = request.vis_announce_loan_disbursement_updates
    if request.vis_show_transfer_receipts is not None:
        settings.vis_show_transfer_receipts = request.vis_show_transfer_receipts
    if request.vis_announce_admin_transactions is not None:
        settings.vis_announce_admin_transactions = request.vis_announce_admin_transactions



    session.add(settings)
    session.commit()
    return {"status": "success", "message": "Transaction messages visibility updated successfully."}
