import json
import time
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.core.group import Group
from app.models.group.core.group_membership import GroupMembership
from app.models.user.user import User
from app.models.group.target_savings import (
    TargetSavingsGroupDetails,
    TargetSavingsPayoutApproval,
    TargetSavingsPayoutProposal,
)
from app.models.group.chat import GroupPoll
from app.models.user.payout_destination.user_payout_destination import UserPayoutDestination
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .schemas import EarlyPayoutProposalRequest

router = APIRouter()


def _validate_payout_readiness(
    session: Session,
    group_id: str,
    details: TargetSavingsGroupDetails,
) -> None:
    members = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.status == "ACTIVE",
        )
    ).all()
    if not members:
        raise HTTPException(status_code=409, detail="This group has no active members.")

    missing_kyc_user_ids = []
    for member in members:
        user = session.get(User, member.user_id)
        if not user or user.kyc_tier < details.minimum_kyc_tier:
            missing_kyc_user_ids.append(str(member.user_id))
    if missing_kyc_user_ids:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Every active member must meet the group's minimum KYC tier before payout.",
                "minimum_kyc_tier": details.minimum_kyc_tier,
                "missing_user_ids": missing_kyc_user_ids,
            },
        )

    if details.allow_multi_payout:
        missing_destination_user_ids = []
        for member in members:
            destination = (
                session.get(UserPayoutDestination, member.payout_destination_id)
                if member.payout_destination_id
                else None
            )
            if (
                not destination
                or destination.user_id != member.user_id
                or not destination.is_verified
            ):
                missing_destination_user_ids.append(str(member.user_id))
        if missing_destination_user_ids:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Every active member must select a verified payout destination before payout.",
                    "missing_user_ids": missing_destination_user_ids,
                },
            )
        return

    if not details.nominated_account_id:
        raise HTTPException(
            status_code=409,
            detail="The single payout destination has not been proposed and approved.",
        )
    try:
        proposal_id = uuid.UUID(details.nominated_account_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail="The saved payout proposal is invalid.",
        ) from exc

    proposal = session.get(TargetSavingsPayoutProposal, proposal_id)
    if not proposal or proposal.group_id != group_id:
        raise HTTPException(
            status_code=409,
            detail="The single payout destination has not been proposed and approved.",
        )

    active_member_ids = {member.user_id for member in members}
    approvals = session.exec(
        select(TargetSavingsPayoutApproval).where(
            TargetSavingsPayoutApproval.proposal_id == proposal_id,
            TargetSavingsPayoutApproval.approved == True,
        )
    ).all()
    approved_member_ids = {approval.user_id for approval in approvals} & active_member_ids
    missing_approval_user_ids = active_member_ids - approved_member_ids
    if missing_approval_user_ids:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Every active member must approve the single payout destination before payout.",
                "missing_user_ids": [str(user_id) for user_id in missing_approval_user_ids],
            },
        )


@router.post("/{group_id}/request-payout", summary="Request a Vote to Release Current Goal Savings")
@router.post("/{group_id}/request-early-payout", include_in_schema=False)
def request_early_payout(
    group_id: str,
    request: EarlyPayoutProposalRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Proposes releasing the current savings balance without ending the group.
    """
    # 1. Verify Active Membership
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You must be an active member to request early payout.")

    details = session.exec(
        select(TargetSavingsGroupDetails).where(TargetSavingsGroupDetails.group_id == group_id)
    ).first()
    if not details:
        raise HTTPException(status_code=404, detail="Target savings details not found.")

    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group or group.type != "GOAL_SAVINGS":
        raise HTTPException(status_code=404, detail="Target savings group not found.")

    if details.is_ended:
        raise HTTPException(status_code=400, detail="This savings group has already ended.")

    target_reached = (
        (details.allow_target_amount and details.target_amount is not None
         and details.total_saved_amount >= details.target_amount)
        or (details.allow_target_date and details.target_date is not None
            and int(time.time() * 1000) >= details.target_date)
    )
    if not target_reached and not details.allow_early_payout_by_vote:
        raise HTTPException(
            status_code=400,
            detail="Early payout requests are disabled until a configured goal or date is reached.",
        )

    _validate_payout_readiness(session, group_id, details)

    # 2. Create a group vote; passing it requests release but does not close the group.
    now_ms = int(time.time() * 1000)
    expires_at = now_ms + (24 * 3600 * 1000) # 24 hours voting window
    poll = GroupPoll(
        group_id=group_id,
        creator_id=current_user.id,
        question=f"Release the current goal savings and continue this group? Reason: {request.reason}",
        options=json.dumps(["Approve Payout", "Keep Saving"]),
        poll_type="GOAL_PAYOUT_REQUEST",
        status="OPEN",
        expires_at=expires_at,
        created_at=now_ms
    )
    session.add(poll)
    session.commit()
    session.refresh(poll)

    # 3. Broadcast Poll to Group Chat
    broadcast_system_message_sync(
        group_id=group_id,
        message_text=json.dumps({
            "poll_id": str(poll.id),
            "question": poll.question,
            "options": ["Approve Payout", "Keep Saving"],
            "vote_approval_percentage": details.vote_approval_percentage
        }),
        message_type="VOTE",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Payout request proposed. The group remains open after payout.",
        "data": {
            "poll_id": str(poll.id),
            "expires_at": poll.expires_at,
            "vote_approval_percentage": details.vote_approval_percentage
        }
    }
