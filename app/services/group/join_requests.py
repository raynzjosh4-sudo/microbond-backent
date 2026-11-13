from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models.group.core.group import Group
from app.models.group.core.group_membership import GroupMembership
from app.models.group.core.membership_join_request import MembershipJoinRequest
from app.models.group.finance.guarantor_pledge import GuarantorPledge
from app.services.group.authorization import grant_role
from app.services.audit_service import AuditService


def maybe_activate_join_request(
    session: Session,
    join_request: MembershipJoinRequest,
    actor_user_id: UUID,
) -> bool:
    if join_request.requires_guarantor:
        accepted_count = session.exec(
            select(GuarantorPledge.id).where(
                GuarantorPledge.group_id == join_request.group_id,
                GuarantorPledge.borrower_user_id == join_request.user_id,
                GuarantorPledge.status == "ACTIVE",
            )
        ).all()
        if len(accepted_count) < join_request.required_guarantors:
            join_request.public_status = "PENDING_GUARANTOR"
            join_request.guarantor_status = "PENDING"
            session.add(join_request)
            return False
        join_request.guarantor_status = "ACCEPTED"

    if join_request.requires_admin_approval and join_request.admin_status != "APPROVED":
        join_request.public_status = "PENDING_APPROVAL"
        session.add(join_request)
        return False

    if join_request.approved_votes < join_request.required_votes:
        join_request.public_status = "VOTING"
        join_request.voting_status = "PENDING"
        session.add(join_request)
        return False

    group = session.exec(
        select(Group)
        .where(Group.group_id == join_request.group_id)
        .with_for_update()
    ).first()
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found.",
        )
    if group.max_members is not None and group.member_count >= group.max_members:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The group has reached its membership capacity.",
        )

    membership = session.exec(
        select(GroupMembership)
        .where(
            GroupMembership.group_id == join_request.group_id,
            GroupMembership.user_id == join_request.user_id,
        )
        .with_for_update()
    ).first()
    if membership is not None and membership.status == "ACTIVE":
        join_request.public_status = "APPROVED"
        join_request.approved_at = datetime.now(timezone.utc)
        session.add(join_request)
        return True

    if membership is None:
        membership = GroupMembership(
            membership_id=str(uuid4()),
            group_id=join_request.group_id,
            user_id=join_request.user_id,
            role="MEMBER",
            title="Member",
            status="ACTIVE",
            private_settings={},
        )
        session.add(membership)
    else:
        membership.status = "ACTIVE"
        session.add(membership)

    group.member_count += 1
    session.add(group)
    grant_role(
        session,
        join_request.group_id,
        join_request.user_id,
        "MEMBER",
        group.created_by_user_id,
    )
    join_request.public_status = "APPROVED"
    join_request.approved_at = datetime.now(timezone.utc)
    join_request.updated_at = datetime.now(timezone.utc)
    session.add(join_request)
    AuditService.record_event(
        session=session,
        action="JOIN_REQUEST_APPROVED",
        entity_type="membership_join_request",
        entity_id=str(join_request.id),
        payload={"user_id": str(join_request.user_id)},
        actor_user_id=actor_user_id,
        tenant_group_id=join_request.group_id,
    )
    return True
