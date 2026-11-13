from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupGovernanceSettings, GroupVisibilitySettings
from app.models.group.rotating import RotatingGroupDetails
from app.models.group.core.membership_join_request import MembershipJoinRequest
from app.models.group.finance import MemberObligation
from app.models.group.finance import GuarantorPledge
from app.core.firebase_config import send_push_notification
from app.core.microbond_core import check_join_rules
from app.core.db_idempotency import begin_db_command, complete_db_command
from app.services.audit_service import AuditService
from app.services.group.authorization import grant_role, require_permission
from app.services.group.join_requests import maybe_activate_join_request
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, timezone
from decimal import Decimal
import uuid
import json
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/groups/join", tags=["Group Join Requests"])


class GroupJoinRequest(BaseModel):
    group_id: Optional[str] = Field(default=None, description="The UUID of the group (used for public groups)")
    invite_code: Optional[str] = Field(default=None, description="The unique 8-character invite code (used for private groups)")
    guarantor_ids: Optional[List[str]] = Field(default_factory=list, description="List of UUIDs of active group members vouching for this user")
    client_request_id: Optional[str] = Field(default=None, description="Unique client-generated idempotency key (UUIDv4) to prevent double joins on retries")


class JoinRequestRejection(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


@router.post("/")
def join_group(
    request: GroupJoinRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if not request.group_id and not request.invite_code:
        raise HTTPException(status_code=400, detail="Must provide either group_id or invite_code.")

    # 1. Authoritative Idempotency Check (FOR UPDATE)
    cached_command = begin_db_command(
        session,
        current_user.id,
        request.client_request_id,
    )
    if cached_command is not None:
        return cached_command.response_payload

    # 2. Base Authentication & Group Lookup (With Row-Level Lock to prevent race conditions)
    if request.invite_code:
        group = session.exec(select(Group).where(Group.invite_code == request.invite_code).with_for_update()).first()
        if not group:
            raise HTTPException(status_code=404, detail="Invalid invite code.")
    else:
        group = session.exec(select(Group).where(Group.group_id == request.group_id).with_for_update()).first()
        if not group:
            raise HTTPException(status_code=404, detail="Group not found.")
        if group.visibility == "PRIVATE":
            raise HTTPException(status_code=403, detail="This is a private group. You must use an invite code to join.")
        vis_settings = session.exec(
            select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group.group_id)
        ).first()
        if vis_settings and vis_settings.invite_only_discoverability:
            raise HTTPException(
                status_code=403,
                detail="This group is invite-only. You must use a direct invite link or invite code to join."
            )

    # 3. Load facts for authoritative domain evaluation
    existing_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group.group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    existing_join_request = session.exec(
        select(MembershipJoinRequest).where(
            MembershipJoinRequest.group_id == group.group_id,
            MembershipJoinRequest.user_id == current_user.id,
            MembershipJoinRequest.public_status.notin_(
                ["APPROVED", "REJECTED", "CANCELLED", "EXPIRED"]
            ),
        )
    ).first()

    if existing_membership and existing_membership.status == "ACTIVE":
        raise HTTPException(status_code=409, detail="You are already an active group member.")
    if existing_join_request is not None:
        raise HTTPException(
            status_code=409,
            detail="You already have an open join request for this group.",
        )
    if existing_membership and existing_membership.status in {
        "PENDING_APPROVAL",
        "PENDING_GUARANTOR",
    }:
        raise HTTPException(
            status_code=409,
            detail="A pending join request already exists for this group.",
        )

    has_arrears = session.exec(
        select(MemberObligation).where(
            MemberObligation.user_id == current_user.id,
            MemberObligation.status.in_(["OVERDUE", "DEFAULTED"])
        )
    ).first() is not None

    settings = session.exec(
        select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group.group_id)
    ).first()

    required_kyc_tier = settings.minimum_kyc_tier if settings else 1
    if group.type == "MERRY_GO_ROUND":
        rotating_details = session.exec(
            select(RotatingGroupDetails).where(RotatingGroupDetails.group_id == group.group_id)
        ).first()
        if rotating_details and hasattr(rotating_details, "minimum_kyc_tier"):
            required_kyc_tier = max(
                required_kyc_tier,
                getattr(rotating_details, "minimum_kyc_tier", 0) or 0,
            )

    requires_guarantor = bool(settings and settings.require_guarantors)
    requires_admin_approval = bool(settings and settings.requires_admin_approval)
    minimum_trust = settings.minimum_trust_score if settings else None

    guarantor_ids: list[uuid.UUID] = []
    if requires_guarantor:
        required_guarantors = max(1, settings.guarantor_count)
        if len(request.guarantor_ids or []) != required_guarantors:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Select exactly {required_guarantors} guarantor(s).",
            )
        try:
            guarantor_ids = [uuid.UUID(gid) for gid in request.guarantor_ids or []]
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Each guarantor ID must be a valid UUID.",
            ) from exc
        if current_user.id in guarantor_ids or len(set(guarantor_ids)) != len(guarantor_ids):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Guarantors must be distinct users other than the applicant.",
            )

        active_guarantors = set(
            session.exec(
                select(GroupMembership.user_id).where(
                    GroupMembership.group_id == group.group_id,
                    GroupMembership.user_id.in_(guarantor_ids),
                    GroupMembership.status == "ACTIVE",
                )
            ).all()
        )
        if active_guarantors != set(guarantor_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Every guarantor must be an active member of this group.",
            )

    # 4. Invoke the deterministic Rust domain engine
    raw_decision = check_join_rules(
        member_count=group.member_count,
        max_members=group.max_members,
        already_member_or_pending=False,
        has_arrears=has_arrears,
        trust_score=current_user.trust_score or 0,
        minimum_trust_score=minimum_trust,
        kyc_tier=current_user.kyc_tier or 0,
        required_kyc_tier=required_kyc_tier,
        requires_guarantor=requires_guarantor,
        requires_admin_approval=requires_admin_approval,
    )
    decision = json.loads(raw_decision)

    if decision.get("status") == "REJECTED":
        reason = decision.get("reason_message") or "Join request was rejected by group governance rules."
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)

    final_status = decision.get("status", "ACTIVE")

    now = datetime.now(timezone.utc)
    join_request = MembershipJoinRequest(
        group_id=group.group_id,
        user_id=current_user.id,
        public_status="APPROVED" if final_status == "ACTIVE" else final_status,
        guarantor_status="PENDING" if requires_guarantor else "NOT_REQUIRED",
        admin_status="PENDING" if requires_admin_approval else "NOT_REQUIRED",
        requires_guarantor=requires_guarantor,
        required_guarantors=max(1, settings.guarantor_count) if requires_guarantor else 0,
        requires_admin_approval=requires_admin_approval,
        submitted_at=now,
        approved_at=now if final_status == "ACTIVE" else None,
    )
    session.add(join_request)
    session.flush()

    # A pending applicant is not an active membership. Membership activation
    # happens only after all configured join requirements have been satisfied.
    if final_status == "ACTIVE":
        new_membership = GroupMembership(
            membership_id=str(uuid.uuid4()),
            group_id=group.group_id,
            user_id=current_user.id,
            role="MEMBER",
            title="Member",
            status="ACTIVE",
            private_settings={},
        )
        session.add(new_membership)
        grant_role(
            session,
            group.group_id,
            current_user.id,
            "MEMBER",
            group.created_by_user_id,
        )
        group.member_count += 1

    # 6. Bind Guarantor Pledges if applicable (with anti-collusion DAG verification)
    if requires_guarantor and request.guarantor_ids:
        from app.models.group.finance import GuarantorPledge
        from app.core.microbond_core import detect_guarantor_cycle

        # Fetch active pledges across groups to construct the directed vouching graph
        existing_pledges = session.exec(
            select(GuarantorPledge.guarantor_user_id, GuarantorPledge.borrower_user_id).where(
                GuarantorPledge.status.in_(["ACTIVE", "PENDING_CONSENT"])
            )
        ).all()
        edges = [(str(p[0]), str(p[1])) for p in existing_pledges]

        for gid in guarantor_ids:
            if detect_guarantor_cycle(edges, str(gid), str(current_user.id)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Circular guarantor collusion detected: member {gid} cannot guarantee your account without creating a circular risk loop."
                )

        pledge_liability = 0
        if group.type == "MERRY_GO_ROUND":
            rotating_details = session.exec(
                select(RotatingGroupDetails).where(RotatingGroupDetails.group_id == group.group_id)
            ).first()
            if (
                rotating_details
                and rotating_details.contribution_amount is not None
                and rotating_details.number_of_cycles is not None
            ):
                total_liability = (
                    Decimal(str(rotating_details.contribution_amount))
                    * rotating_details.number_of_cycles
                )
                pledge_liability = int(total_liability // len(guarantor_ids))

        for gid in guarantor_ids:
            new_pledge = GuarantorPledge(
                group_id=group.group_id,
                guarantor_user_id=gid,
                borrower_user_id=current_user.id,
                maximum_liability_amount=pledge_liability,
                status="PENDING_CONSENT"
            )
            session.add(new_pledge)

    # 7. Construct authoritative response payload
    response_payload = {
        "status": "success",
        "message": "Joined successfully!" if final_status == "ACTIVE" else "Join request sent for approval.",
        "membership_status": final_status,
        "group_id": group.group_id,
        "join_request_id": str(join_request.id),
    }

    # 8. Record audit event and idempotency in the same transaction
    AuditService.record_event(
        session=session,
        action="JOIN_REQUESTED",
        entity_type="GROUP",
        entity_id=group.group_id,
        payload={
            "user_id": str(current_user.id),
            "membership_status": final_status,
            "join_request_id": str(join_request.id),
            "decision": decision
        },
        actor_user_id=current_user.id,
        tenant_group_id=group.group_id,
    )

    complete_db_command(
        session=session,
        user_id=current_user.id,
        client_request_id=request.client_request_id,
        response_payload=response_payload
    )
    if final_status == "ACTIVE":
        from app.models.group.chat import GroupChatMessage
        spots_str = f"{group.member_count} of {group.max_members or '?'} spots filled"
        join_msg = GroupChatMessage(
            client_message_id=str(uuid.uuid4()),
            group_id=group.group_id,
            sender_id="SYSTEM",
            message_type="SYSTEM_EVENT",
            message_text=f"{current_user.full_name} joined the group ({spots_str}).",
            status="SENT"
        )
        session.add(join_msg)

    session.commit()

    # If capacity is reached for a rotating group, auto-launch the schedule
    if final_status == "ACTIVE" and group.max_members and group.member_count >= group.max_members:
        if group.type == "MERRY_GO_ROUND":
            from app.services.group.launcher_service import execute_group_launch
            try:
                execute_group_launch(session, group.group_id)
                session.commit()
            except Exception as e:
                logger.warning(f"Auto-launch notice: {e}")

    # Event 2: Push broadcast to all other active members
    if final_status == "ACTIVE":
        spots_left = max(0, (group.max_members or 0) - group.member_count) if group.max_members else "?"
        try:
            from app.services.push_notifications import notify_all_group_members_sync
            notify_all_group_members_sync(
                group_id=group.group_id,
                sender_id=str(current_user.id),
                title="👥 New Member Joined",
                body=f"{current_user.full_name} joined {group.name}! {group.member_count} of {group.max_members or '?'} members confirmed. {spots_left} spots left before kickoff.",
                data={"route": "group_dashboard", "group_id": group.group_id}
            )
        except Exception as push_err:
            logger.warning(f"[JOIN PUSH BROADCAST] Failed: {push_err}")

    # 9. Asynchronous Push Notifications after commit
    if final_status == "PENDING_APPROVAL":
        admin_memberships = session.exec(
            select(GroupMembership).where(
                GroupMembership.group_id == group.group_id,
                GroupMembership.role == "ADMIN",
                GroupMembership.status == "ACTIVE"
            )
        ).all()
        admin_users = session.exec(
            select(User).where(User.id.in_([m.user_id for m in admin_memberships]))
        ).all()
        for admin in admin_users:
            if admin.fcm_token:
                send_push_notification(
                    token=admin.fcm_token,
                    title="New Join Request 🙋",
                    body=f"{current_user.full_name} wants to join '{group.name}'. Tap to review.",
                    data={"type": "JOIN_REQUEST_PENDING", "group_id": group.group_id}
                )

    if requires_guarantor and guarantor_ids:
        for gid in guarantor_ids:
            try:
                guarantor = session.get(User, uuid.UUID(gid))
                if guarantor and guarantor.fcm_token:
                    send_push_notification(
                        token=guarantor.fcm_token,
                        title="Guarantor Request 🤝",
                        body=f"{current_user.full_name} listed you as a guarantor to join '{group.name}'. Tap to review.",
                        data={"type": "GUARANTOR_REQUEST", "group_id": group.group_id}
                    )
            except Exception as push_error:
                logger.warning("Failed to notify guarantor %s: %s", gid, push_error)

    return response_payload


@router.post("/{join_request_id}/approve")
def approve_group_join_request(
    join_request_id: uuid.UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    join_request = session.exec(
        select(MembershipJoinRequest)
        .where(MembershipJoinRequest.id == join_request_id)
        .with_for_update()
    ).first()
    if join_request is None:
        raise HTTPException(status_code=404, detail="Join request not found.")
    require_permission(
        session,
        current_user.id,
        join_request.group_id,
        "MANAGE_MEMBERS",
    )
    if not join_request.requires_admin_approval:
        raise HTTPException(
            status_code=409,
            detail="This join request does not require admin approval.",
        )
    if join_request.public_status not in {"PENDING_APPROVAL", "PENDING_GUARANTOR", "VOTING"}:
        raise HTTPException(status_code=409, detail="Join request is no longer pending.")

    join_request.admin_status = "APPROVED"
    join_request.updated_at = datetime.now(timezone.utc)
    session.add(join_request)
    activated = maybe_activate_join_request(
        session,
        join_request,
        current_user.id,
    )
    AuditService.record_event(
        session=session,
        action="JOIN_REQUEST_ADMIN_APPROVED",
        entity_type="membership_join_request",
        entity_id=str(join_request.id),
        payload={"activated": activated},
        actor_user_id=current_user.id,
        tenant_group_id=join_request.group_id,
    )
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise

    return {
        "status": "success",
        "join_request_id": str(join_request.id),
        "membership_status": join_request.public_status,
        "activated": activated,
    }


@router.post("/{join_request_id}/reject")
def reject_group_join_request(
    join_request_id: uuid.UUID,
    request: JoinRequestRejection,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    join_request = session.exec(
        select(MembershipJoinRequest)
        .where(MembershipJoinRequest.id == join_request_id)
        .with_for_update()
    ).first()
    if join_request is None:
        raise HTTPException(status_code=404, detail="Join request not found.")
    require_permission(
        session,
        current_user.id,
        join_request.group_id,
        "MANAGE_MEMBERS",
    )
    if join_request.public_status not in {"PENDING_APPROVAL", "PENDING_GUARANTOR", "VOTING"}:
        raise HTTPException(status_code=409, detail="Join request is no longer pending.")

    now = datetime.now(timezone.utc)
    join_request.public_status = "REJECTED"
    join_request.admin_status = "REJECTED"
    join_request.rejection_reason = request.reason
    join_request.rejected_at = now
    join_request.updated_at = now
    pending_pledges = session.exec(
        select(GuarantorPledge).where(
            GuarantorPledge.group_id == join_request.group_id,
            GuarantorPledge.borrower_user_id == join_request.user_id,
            GuarantorPledge.status == "PENDING_CONSENT",
        )
    ).all()
    for pledge in pending_pledges:
        pledge.status = "REJECTED"
        session.add(pledge)
    session.add(join_request)
    AuditService.record_event(
        session=session,
        action="JOIN_REQUEST_REJECTED",
        entity_type="membership_join_request",
        entity_id=str(join_request.id),
        payload={"reason": request.reason},
        actor_user_id=current_user.id,
        tenant_group_id=join_request.group_id,
    )
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise

    return {
        "status": "success",
        "join_request_id": str(join_request.id),
        "membership_status": join_request.public_status,
    }
