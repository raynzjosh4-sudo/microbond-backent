from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.settings import GroupCommunicationSettings

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])

class UpdateTransactionMessagesRequest(BaseModel):
    broadcast_individual_deposit_receipts: Optional[bool] = None
    broadcast_individual_dues_receipts: Optional[bool] = None
    broadcast_individual_loan_receipts: Optional[bool] = None
    announce_payout_updates: Optional[bool] = None
    announce_dues_adjustment_updates: Optional[bool] = None
    announce_loan_disbursement_updates: Optional[bool] = None
    show_transfer_receipts: Optional[bool] = None
    announce_admin_transactions: Optional[bool] = None

@router.patch("/{group_id}/settings/transaction-messages", summary="Admin: Update Transaction Message Settings")
def update_transaction_message_settings(
    group_id: str, 
    request: UpdateTransactionMessagesRequest, 
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
        raise HTTPException(status_code=403, detail="Only the Group Admin can update transaction message settings.")

    settings = session.exec(
        select(GroupCommunicationSettings).where(GroupCommunicationSettings.group_id == group_id)
    ).first()
    
    if not settings:
        raise HTTPException(status_code=404, detail="Communication settings not found.")

    if request.broadcast_individual_deposit_receipts is not None:
        settings.broadcast_individual_deposit_receipts = request.broadcast_individual_deposit_receipts
    if request.broadcast_individual_dues_receipts is not None:
        settings.broadcast_individual_dues_receipts = request.broadcast_individual_dues_receipts
    if request.broadcast_individual_loan_receipts is not None:
        settings.broadcast_individual_loan_receipts = request.broadcast_individual_loan_receipts
        
    if request.announce_payout_updates is not None:
        settings.announce_payout_updates = request.announce_payout_updates
    if request.announce_dues_adjustment_updates is not None:
        settings.announce_dues_adjustment_updates = request.announce_dues_adjustment_updates
    if request.announce_loan_disbursement_updates is not None:
        settings.announce_loan_disbursement_updates = request.announce_loan_disbursement_updates
        
    if request.show_transfer_receipts is not None:
        settings.show_transfer_receipts = request.show_transfer_receipts
        
    if request.announce_admin_transactions is not None:
        settings.announce_admin_transactions = request.announce_admin_transactions


    session.add(settings)
    session.commit()
    return {"status": "success", "message": "Transaction message settings updated successfully."}
