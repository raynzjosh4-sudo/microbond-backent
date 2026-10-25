import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import Optional

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.finance import GroupPayout
from app.models.group.rotating import RotatingGroupDetails
from app.cronjobs.finance.payout_disbursement_worker.process_single_payout import process_single_payout
from app.utils.time.now_epoch_ms import now_epoch_ms

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/{group_id}/payouts/{payout_id}/disburse", summary="Manually Release / Disburse Payout")
def manually_disburse_payout(
    group_id: str,
    payout_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Allows the Group Admin or Treasurer to manually trigger payout disbursement
    when auto_disburse_when_full is False or when Multi-Sig approval is completed.
    """
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()

    if not membership or membership.role not in ["ADMIN", "TREASURER"]:
        raise HTTPException(status_code=403, detail="Only the Group Admin or Treasurer can release payouts.")

    payout = session.exec(
        select(GroupPayout).where(
            GroupPayout.id == payout_id,
            GroupPayout.group_id == group_id
        )
    ).first()

    if not payout:
        raise HTTPException(status_code=404, detail="Payout record not found.")

    if payout.status == "COMPLETED":
        raise HTTPException(status_code=400, detail="This payout has already been completed.")

    rotating = session.exec(
        select(RotatingGroupDetails).where(RotatingGroupDetails.group_id == group_id)
    ).first()

    if rotating and rotating.multi_sig_payout_approval:
        if payout.status != "APPROVED_FOR_DISBURSEMENT" and membership.role != "ADMIN":
            raise HTTPException(
                status_code=403,
                detail="Multi-signature approval required before this payout can be disbursed."
            )

    now_ms = now_epoch_ms()
    payout.status = "APPROVED_FOR_DISBURSEMENT"
    session.add(payout)
    session.commit()

    # Execute disbursement immediately with force_disburse override
    process_single_payout(session=session, payout=payout, now_ms=now_ms, force_disburse=True)

    session.refresh(payout)
    return {
        "status": "success",
        "message": f"Payout of {payout.amount_received:,} UGX processed successfully.",
        "data": {
            "payout_id": payout.id,
            "status": payout.status,
            "amount_received": payout.amount_received,
            "cycle_number": payout.cycle_number
        }
    }


@router.post("/{group_id}/payouts/{payout_id}/sign", summary="Sign / Approve Multi-Sig Payout")
def sign_multisig_payout(
    group_id: str,
    payout_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Allows designated signers (Admin and Treasurer) to co-sign an upcoming payout.
    When approved, marks payout status as APPROVED_FOR_DISBURSEMENT.
    """
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()

    if not membership or membership.role not in ["ADMIN", "TREASURER"]:
        raise HTTPException(status_code=403, detail="Only authorized signers (Admin/Treasurer) can sign payouts.")

    payout = session.exec(
        select(GroupPayout).where(
            GroupPayout.id == payout_id,
            GroupPayout.group_id == group_id
        )
    ).first()

    if not payout:
        raise HTTPException(status_code=404, detail="Payout record not found.")

    payout.status = "APPROVED_FOR_DISBURSEMENT"
    payout.hold_reason = f"Signed and approved by {membership.role} {current_user.full_name}."
    session.add(payout)
    session.commit()
    session.refresh(payout)

    return {
        "status": "success",
        "message": f"Payout signed and approved by {membership.role}.",
        "data": {
            "payout_id": payout.id,
            "status": payout.status
        }
    }
