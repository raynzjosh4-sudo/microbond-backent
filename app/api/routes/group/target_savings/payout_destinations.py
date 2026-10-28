import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.dependencies import get_current_user
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from app.core.database import get_session
from app.models.group.core.group import Group
from app.models.group.core.group_membership import GroupMembership
from app.models.group.target_savings import (
    TargetSavingsGroupDetails,
    TargetSavingsPayoutApproval,
    TargetSavingsPayoutProposal,
)
from app.models.user.payout_destination.user_payout_destination import UserPayoutDestination
from app.models.user.user import User
from .schemas.payout_destination_requests import (
    ApproveSinglePayoutDestinationRequest,
    ProposeSinglePayoutDestinationRequest,
    SetMemberPayoutDestinationRequest,
)

router = APIRouter()


def _active_member(session: Session, group_id: str, user_id: uuid.UUID) -> GroupMembership:
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user_id,
            GroupMembership.status == "ACTIVE",
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You must be an active group member.")
    return membership


def _goal_details(session: Session, group_id: str) -> TargetSavingsGroupDetails:
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group or group.type != "GOAL_SAVINGS":
        raise HTTPException(status_code=404, detail="Target savings group not found.")
    details = session.exec(
        select(TargetSavingsGroupDetails).where(
            TargetSavingsGroupDetails.group_id == group_id
        )
    ).first()
    if not details:
        raise HTTPException(status_code=404, detail="Target savings settings not found.")
    return details


def _proposal_summary(
    session: Session,
    group_id: str,
    details: TargetSavingsGroupDetails,
    current_user_id: uuid.UUID | None = None,
) -> dict:
    proposal_id = details.nominated_account_id
    proposal = None
    if proposal_id:
        try:
            proposal = session.get(TargetSavingsPayoutProposal, uuid.UUID(proposal_id))
        except ValueError:
            proposal = None

    if not proposal or proposal.group_id != group_id:
        return {
            "proposal": None,
            "approved_count": 0,
            "required_count": len(session.exec(
                select(GroupMembership).where(
                    GroupMembership.group_id == group_id,
                    GroupMembership.status == "ACTIVE",
                )
            ).all()),
            "approved_user_ids": [],
            "missing_user_ids": [],
            "is_approved": False,
            "current_user_approved": False,
        }

    members = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.status == "ACTIVE",
        )
    ).all()
    approvals = session.exec(
        select(TargetSavingsPayoutApproval).where(
            TargetSavingsPayoutApproval.proposal_id == proposal.id,
            TargetSavingsPayoutApproval.approved == True,
        )
    ).all()
    approved_ids = {approval.user_id for approval in approvals}
    member_ids = {member.user_id for member in members}
    approved_member_ids = approved_ids & member_ids
    missing_ids = member_ids - approved_member_ids

    return {
        "proposal": {
            "id": str(proposal.id),
            "provider_name": proposal.provider_name,
            "account_type": proposal.account_type,
            "account_number": proposal.account_number,
            "account_name": proposal.account_name,
            "created_by_user_id": str(proposal.created_by_user_id),
            "status": "APPROVED" if not missing_ids else "PENDING",
        },
        "approved_count": len(approved_member_ids),
        "required_count": len(member_ids),
        "approved_user_ids": [str(user_id) for user_id in approved_member_ids],
        "missing_user_ids": [str(user_id) for user_id in missing_ids],
        "is_approved": bool(member_ids) and not missing_ids,
        "current_user_approved": current_user_id in approved_member_ids,
    }


@router.get("/{group_id}/payout-destination")
def get_payout_destination_status(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    _active_member(session, group_id, current_user.id)
    details = _goal_details(session, group_id)
    if details.allow_multi_payout:
        raise HTTPException(
            status_code=409,
            detail="This group uses individual member payout destinations.",
        )
    return {
        "status": "success",
        "data": _proposal_summary(session, group_id, details, current_user.id),
    }


@router.put("/{group_id}/payout-destination")
def propose_single_payout_destination(
    group_id: str,
    request: ProposeSinglePayoutDestinationRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    admin = _active_member(session, group_id, current_user.id)
    if admin.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only an active group admin may set this account.")
    details = _goal_details(session, group_id)
    if details.allow_multi_payout:
        raise HTTPException(
            status_code=409,
            detail="Switch the group to single-account payout before proposing a destination.",
        )

    proposal = TargetSavingsPayoutProposal(
        group_id=group_id,
        created_by_user_id=current_user.id,
        provider_name=request.provider_name.strip(),
        account_type=request.account_type,
        account_number=request.account_number.strip(),
        account_name=request.account_name.strip(),
        status="PENDING",
    )
    session.add(proposal)
    session.flush()
    details.nominated_account_id = str(proposal.id)
    session.add(details)
    session.commit()
    session.refresh(proposal)

    broadcast_system_message_sync(
        group_id=group_id,
        message_text="The group admin proposed a single payout destination. Review the destination and approve it.",
        message_type="SYSTEM_EVENT",
        sender_id="SYSTEM",
        session=session,
        attachments=[{
            "category": "GOAL_PAYOUT_DESTINATION",
            "proposal_id": str(proposal.id),
        }],
    )

    return {
        "status": "success",
        "message": "Payout destination proposed. Each active member must approve it.",
        "data": _proposal_summary(session, group_id, details, current_user.id),
    }


@router.post("/{group_id}/payout-destination/approval")
def set_single_payout_destination_approval(
    group_id: str,
    request: ApproveSinglePayoutDestinationRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    _active_member(session, group_id, current_user.id)
    details = _goal_details(session, group_id)
    if details.allow_multi_payout or not details.nominated_account_id:
        raise HTTPException(status_code=409, detail="There is no single payout destination to approve.")
    try:
        proposal_id = uuid.UUID(details.nominated_account_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="The saved payout proposal is invalid.") from exc

    proposal = session.get(TargetSavingsPayoutProposal, proposal_id)
    if not proposal or proposal.group_id != group_id:
        raise HTTPException(status_code=404, detail="Payout destination proposal not found.")

    approval = session.get(
        TargetSavingsPayoutApproval,
        (proposal_id, current_user.id),
    )
    if approval:
        approval.approved = request.approved
    else:
        approval = TargetSavingsPayoutApproval(
            proposal_id=proposal_id,
            user_id=current_user.id,
            approved=request.approved,
        )
    session.add(approval)
    session.flush()

    summary = _proposal_summary(session, group_id, details, current_user.id)
    proposal.status = "APPROVED" if summary["is_approved"] else "PENDING"
    session.add(proposal)
    session.commit()

    return {
        "status": "success",
        "message": "Payout destination approval recorded.",
        "data": summary,
    }


@router.get("/{group_id}/my-payout-destination")
def get_my_payout_destination(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    membership = _active_member(session, group_id, current_user.id)
    details = _goal_details(session, group_id)
    if not details.allow_multi_payout:
        raise HTTPException(
            status_code=409,
            detail="This group uses a single approved payout destination.",
        )

    destination = None
    if membership.payout_destination_id:
        destination = session.exec(
            select(UserPayoutDestination).where(
                UserPayoutDestination.id == membership.payout_destination_id,
                UserPayoutDestination.user_id == current_user.id,
            )
        ).first()

    return {
        "status": "success",
        "data": {
            "payout_destination_id": destination.id if destination else None,
            "provider_name": destination.provider_name if destination else None,
            "account_type": destination.account_type if destination else None,
            "account_name": destination.verified_name or destination.account_name if destination else None,
            "account_number": destination.account_number if destination else None,
            "is_verified": destination.is_verified if destination else False,
            "destination_required": destination is None,
        },
    }


@router.put("/{group_id}/my-payout-destination")
def set_my_payout_destination(
    group_id: str,
    request: SetMemberPayoutDestinationRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    membership = _active_member(session, group_id, current_user.id)
    details = _goal_details(session, group_id)
    if not details.allow_multi_payout:
        raise HTTPException(
            status_code=409,
            detail="This group uses a single approved payout destination.",
        )

    destination = session.exec(
        select(UserPayoutDestination).where(
            UserPayoutDestination.id == request.payout_destination_id,
            UserPayoutDestination.user_id == current_user.id,
        )
    ).first()
    if not destination:
        raise HTTPException(status_code=400, detail="Payout destination does not belong to you.")

    membership.payout_destination_id = destination.id
    session.add(membership)
    session.commit()
    return {
        "status": "success",
        "message": "Your payout destination was saved for this goal-savings group.",
        "data": {"payout_destination_id": destination.id},
    }
