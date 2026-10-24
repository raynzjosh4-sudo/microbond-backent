from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupCommunicationSettings, GroupVisibilitySettings
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/v1/groups", tags=["Group Settings"])


class UpdateTransactionMessagesRequest(BaseModel):
    # Core toggles (with aliases matching mobile UI)
    broadcast_individual_deposit_receipts: Optional[bool] = Field(default=None, description="Show deposit receipts in chat")
    broadcast_individual_contribution_receipts: Optional[bool] = Field(default=None, description="UI alias for deposit receipts in savings groups")
    announce_payout_updates: Optional[bool] = Field(default=None, description="Announce payout or disbursement updates in chat")
    announce_approved_withdrawal_updates: Optional[bool] = Field(default=None, description="UI alias for approved withdrawal updates")
    show_transfer_receipts: Optional[bool] = Field(default=None, description="Include wallet top-ups and member transfers")
    announce_admin_transactions: Optional[bool] = Field(default=None, description="Announce confirmed and authorized admin transactions")

    # Group-type specific message toggles
    broadcast_individual_dues_receipts: Optional[bool] = Field(default=None, description="Show dues receipts in chat")
    broadcast_individual_loan_receipts: Optional[bool] = Field(default=None, description="Show loan repayment receipts in chat")
    announce_dues_adjustment_updates: Optional[bool] = Field(default=None, description="Announce dues rate/policy adjustments")
    announce_loan_disbursement_updates: Optional[bool] = Field(default=None, description="Announce loan disbursements")

    # Member visibility toggles (allows syncing visibility directly from this screen)
    vis_broadcast_individual_deposit_receipts: Optional[bool] = None
    vis_broadcast_individual_contribution_receipts: Optional[bool] = None
    vis_announce_payout_updates: Optional[bool] = None
    vis_announce_approved_withdrawal_updates: Optional[bool] = None
    vis_show_transfer_receipts: Optional[bool] = None
    vis_announce_admin_transactions: Optional[bool] = None
    vis_broadcast_individual_dues_receipts: Optional[bool] = None
    vis_broadcast_individual_loan_receipts: Optional[bool] = None
    vis_announce_dues_adjustment_updates: Optional[bool] = None
    vis_announce_loan_disbursement_updates: Optional[bool] = None


@router.get("/{group_id}/settings/transaction-messages", summary="Get Transaction Message Settings")
@router.get("/{group_id}/settings/contribution-messages", summary="Get Contribution Message Settings")
def get_transaction_message_settings(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns the current transaction / contribution message broadcast settings,
    including member visibility states and formatted UI item models.
    """
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You must be a member of this group to view settings.")

    is_admin = (membership.role == "ADMIN")

    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    comm = session.exec(
        select(GroupCommunicationSettings).where(GroupCommunicationSettings.group_id == group_id)
    ).first()
    if not comm:
        comm = GroupCommunicationSettings(group_id=group_id)
        session.add(comm)
        session.commit()
        session.refresh(comm)

    vis = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()
    if not vis:
        vis = GroupVisibilitySettings(group_id=group_id)
        session.add(vis)
        session.commit()
        session.refresh(vis)

    is_savings_group = group.type in ["GOAL_SAVINGS", "MERRY_GO_ROUND", "TARGET_SAVINGS", "WELFARE_FUND", "EVENT_COMMITTEE"]

    deposit_title = "Broadcast individual contribution receipts" if is_savings_group else "Broadcast individual deposit receipts"
    deposit_desc = "Show confirmed contribution receipts in group chat." if is_savings_group else "Show confirmed deposit receipts in group chat."

    payout_title = "Announce approved withdrawal updates" if is_savings_group else "Announce approved payout updates"
    payout_desc = "Post a confirmation when an approved withdrawal is completed." if is_savings_group else "Post a confirmation when an approved payout or disbursement is completed."

    items = [
        {
            "id": "broadcast_individual_deposit_receipts",
            "title": deposit_title,
            "description": deposit_desc,
            "enabled": comm.broadcast_individual_deposit_receipts,
            "visible_to_members": vis.vis_broadcast_individual_deposit_receipts,
            "vis_key": "vis_broadcast_individual_deposit_receipts"
        },
        {
            "id": "announce_payout_updates",
            "title": payout_title,
            "description": payout_desc,
            "enabled": comm.announce_payout_updates,
            "visible_to_members": vis.vis_announce_payout_updates,
            "vis_key": "vis_announce_payout_updates"
        },
        {
            "id": "show_transfer_receipts",
            "title": "Show transfer receipts",
            "description": "Include wallet top-ups and member transfers.",
            "enabled": comm.show_transfer_receipts,
            "visible_to_members": vis.vis_show_transfer_receipts,
            "vis_key": "vis_show_transfer_receipts"
        },
        {
            "id": "announce_admin_transactions",
            "title": "Announce admin transactions",
            "description": "Only confirmed and authorized transactions are announced.",
            "enabled": comm.announce_admin_transactions,
            "visible_to_members": vis.vis_announce_admin_transactions,
            "vis_key": "vis_announce_admin_transactions"
        }
    ]

    if group.type == "INVESTMENT_CLUB":
        items.extend([
            {
                "id": "broadcast_individual_loan_receipts",
                "title": "Broadcast individual loan receipts",
                "description": "Show confirmed loan repayment receipts in group chat.",
                "enabled": comm.broadcast_individual_loan_receipts,
                "visible_to_members": vis.vis_broadcast_individual_loan_receipts,
                "vis_key": "vis_broadcast_individual_loan_receipts"
            },
            {
                "id": "announce_loan_disbursement_updates",
                "title": "Announce loan disbursement updates",
                "description": "Post notice when an approved loan is disbursed to a member.",
                "enabled": comm.announce_loan_disbursement_updates,
                "visible_to_members": vis.vis_announce_loan_disbursement_updates,
                "vis_key": "vis_announce_loan_disbursement_updates"
            }
        ])
    elif group.type == "ASSOCIATION_DUES":
        items.extend([
            {
                "id": "broadcast_individual_dues_receipts",
                "title": "Broadcast individual dues receipts",
                "description": "Show confirmed subscription and dues payments in group chat.",
                "enabled": comm.broadcast_individual_dues_receipts,
                "visible_to_members": vis.vis_broadcast_individual_dues_receipts,
                "vis_key": "vis_broadcast_individual_dues_receipts"
            },
            {
                "id": "announce_dues_adjustment_updates",
                "title": "Announce dues adjustment updates",
                "description": "Post notices when dues structures or late fees are modified.",
                "enabled": comm.announce_dues_adjustment_updates,
                "visible_to_members": vis.vis_announce_dues_adjustment_updates,
                "vis_key": "vis_announce_dues_adjustment_updates"
            }
        ])

    response_data = {
        "group_id": group_id,
        "group_name": group.name,
        "group_type": group.type,
        "member_count": group.member_count or 0,
        "is_admin": is_admin,
        "screen_title": "Contribution messages" if is_savings_group else "Transaction messages",
        "subtitle": group.name.upper(),
        "header_tag": group.type.replace("_", " ").title(),
        "header_members_display": f"{group.member_count or 0} members · confirmed transactions",
        "broadcast_individual_deposit_receipts": comm.broadcast_individual_deposit_receipts,
        "broadcast_individual_contribution_receipts": comm.broadcast_individual_deposit_receipts,
        "announce_payout_updates": comm.announce_payout_updates,
        "announce_approved_withdrawal_updates": comm.announce_payout_updates,
        "show_transfer_receipts": comm.show_transfer_receipts,
        "announce_admin_transactions": comm.announce_admin_transactions,
        "broadcast_individual_dues_receipts": comm.broadcast_individual_dues_receipts,
        "broadcast_individual_loan_receipts": comm.broadcast_individual_loan_receipts,
        "announce_dues_adjustment_updates": comm.announce_dues_adjustment_updates,
        "announce_loan_disbursement_updates": comm.announce_loan_disbursement_updates,
        "visibility_status": {
            "vis_broadcast_individual_deposit_receipts": vis.vis_broadcast_individual_deposit_receipts,
            "vis_broadcast_individual_contribution_receipts": vis.vis_broadcast_individual_deposit_receipts,
            "vis_announce_payout_updates": vis.vis_announce_payout_updates,
            "vis_announce_approved_withdrawal_updates": vis.vis_announce_payout_updates,
            "vis_show_transfer_receipts": vis.vis_show_transfer_receipts,
            "vis_announce_admin_transactions": vis.vis_announce_admin_transactions,
            "vis_broadcast_individual_dues_receipts": vis.vis_broadcast_individual_dues_receipts,
            "vis_broadcast_individual_loan_receipts": vis.vis_broadcast_individual_loan_receipts,
            "vis_announce_dues_adjustment_updates": vis.vis_announce_dues_adjustment_updates,
            "vis_announce_loan_disbursement_updates": vis.vis_announce_loan_disbursement_updates,
        },
        "items": items if is_admin else [item for item in items if item["visible_to_members"]]
    }

    return {
        "status": "success",
        "data": response_data
    }


@router.patch("/{group_id}/settings/transaction-messages", summary="Admin: Update Transaction Message Settings")
@router.patch("/{group_id}/settings/contribution-messages", summary="Admin: Update Contribution Message Settings")
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

    comm = session.exec(
        select(GroupCommunicationSettings).where(GroupCommunicationSettings.group_id == group_id)
    ).first()
    if not comm:
        comm = GroupCommunicationSettings(group_id=group_id)
        session.add(comm)

    vis = session.exec(
        select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)
    ).first()
    if not vis:
        vis = GroupVisibilitySettings(group_id=group_id)
        session.add(vis)

    # Resolve deposit/contribution toggle
    deposit_toggle = request.broadcast_individual_deposit_receipts
    if deposit_toggle is None:
        deposit_toggle = request.broadcast_individual_contribution_receipts
    if deposit_toggle is not None:
        comm.broadcast_individual_deposit_receipts = deposit_toggle

    # Resolve payout/withdrawal toggle
    payout_toggle = request.announce_payout_updates
    if payout_toggle is None:
        payout_toggle = request.announce_approved_withdrawal_updates
    if payout_toggle is not None:
        comm.announce_payout_updates = payout_toggle

    if request.show_transfer_receipts is not None:
        comm.show_transfer_receipts = request.show_transfer_receipts

    if request.announce_admin_transactions is not None:
        comm.announce_admin_transactions = request.announce_admin_transactions

    if request.broadcast_individual_dues_receipts is not None:
        comm.broadcast_individual_dues_receipts = request.broadcast_individual_dues_receipts

    if request.broadcast_individual_loan_receipts is not None:
        comm.broadcast_individual_loan_receipts = request.broadcast_individual_loan_receipts

    if request.announce_dues_adjustment_updates is not None:
        comm.announce_dues_adjustment_updates = request.announce_dues_adjustment_updates

    if request.announce_loan_disbursement_updates is not None:
        comm.announce_loan_disbursement_updates = request.announce_loan_disbursement_updates

    # Member visibility updates (if submitted)
    vis_deposit = request.vis_broadcast_individual_deposit_receipts
    if vis_deposit is None:
        vis_deposit = request.vis_broadcast_individual_contribution_receipts
    if vis_deposit is not None:
        vis.vis_broadcast_individual_deposit_receipts = vis_deposit

    vis_payout = request.vis_announce_payout_updates
    if vis_payout is None:
        vis_payout = request.vis_announce_approved_withdrawal_updates
    if vis_payout is not None:
        vis.vis_announce_payout_updates = vis_payout

    if request.vis_show_transfer_receipts is not None:
        vis.vis_show_transfer_receipts = request.vis_show_transfer_receipts

    if request.vis_announce_admin_transactions is not None:
        vis.vis_announce_admin_transactions = request.vis_announce_admin_transactions

    if request.vis_broadcast_individual_dues_receipts is not None:
        vis.vis_broadcast_individual_dues_receipts = request.vis_broadcast_individual_dues_receipts

    if request.vis_broadcast_individual_loan_receipts is not None:
        vis.vis_broadcast_individual_loan_receipts = request.vis_broadcast_individual_loan_receipts

    if request.vis_announce_dues_adjustment_updates is not None:
        vis.vis_announce_dues_adjustment_updates = request.vis_announce_dues_adjustment_updates

    if request.vis_announce_loan_disbursement_updates is not None:
        vis.vis_announce_loan_disbursement_updates = request.vis_announce_loan_disbursement_updates

    session.add(comm)
    session.add(vis)

    AuditService.record_event(
        session=session,
        action="TRANSACTION_MESSAGES_SETTINGS_UPDATED",
        entity_type="GROUP",
        entity_id=group_id,
        payload={
            "updated_by": str(current_user.id),
            "broadcast_individual_deposit_receipts": comm.broadcast_individual_deposit_receipts,
            "announce_payout_updates": comm.announce_payout_updates,
            "show_transfer_receipts": comm.show_transfer_receipts,
            "announce_admin_transactions": comm.announce_admin_transactions,
            "vis_broadcast_individual_deposit_receipts": vis.vis_broadcast_individual_deposit_receipts,
            "vis_announce_payout_updates": vis.vis_announce_payout_updates,
            "vis_show_transfer_receipts": vis.vis_show_transfer_receipts,
            "vis_announce_admin_transactions": vis.vis_announce_admin_transactions,
        },
        actor_user_id=current_user.id
    )

    session.commit()
    session.refresh(comm)
    session.refresh(vis)

    return {
        "status": "success",
        "message": "Transaction and contribution message settings updated successfully.",
        "data": {
            "broadcast_individual_deposit_receipts": comm.broadcast_individual_deposit_receipts,
            "broadcast_individual_contribution_receipts": comm.broadcast_individual_deposit_receipts,
            "announce_payout_updates": comm.announce_payout_updates,
            "announce_approved_withdrawal_updates": comm.announce_payout_updates,
            "show_transfer_receipts": comm.show_transfer_receipts,
            "announce_admin_transactions": comm.announce_admin_transactions,
            "visibility_status": {
                "vis_broadcast_individual_deposit_receipts": vis.vis_broadcast_individual_deposit_receipts,
                "vis_announce_payout_updates": vis.vis_announce_payout_updates,
                "vis_show_transfer_receipts": vis.vis_show_transfer_receipts,
                "vis_announce_admin_transactions": vis.vis_announce_admin_transactions,
            }
        }
    }
