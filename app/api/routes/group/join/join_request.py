from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.settings import GroupGovernanceSettings, GroupVisibilitySettings
from app.models.group.rotating import RotatingGroupDetails
from app.models.group.finance import MemberObligation
from app.core.firebase_config import send_push_notification
from app.core.microbond_core import check_join_rules
from app.core.db_idempotency import check_db_idempotency, record_db_idempotency
from app.services.audit_service import AuditService
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid
import json

router = APIRouter(prefix="/api/v1/groups/join", tags=["Group Join Requests"])


class GroupJoinRequest(BaseModel):
    group_id: Optional[str] = Field(default=None, description="The UUID of the group (used for public groups)")
    invite_code: Optional[str] = Field(default=None, description="The unique 8-character invite code (used for private groups)")
    guarantor_ids: Optional[List[str]] = Field(default_factory=list, description="List of UUIDs of active group members vouching for this user")
    client_request_id: Optional[str] = Field(default=None, description="Unique client-generated idempotency key (UUIDv4) to prevent double joins on retries")


@router.post("/")
def join_group(
    request: GroupJoinRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    if not request.group_id and not request.invite_code:
        raise HTTPException(status_code=400, detail="Must provide either group_id or invite_code.")

    # 1. Authoritative Idempotency Check (FOR UPDATE)
    cached_response = check_db_idempotency(session, current_user.id, request.client_request_id)
    if cached_response is not None:
        return cached_response

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

    has_arrears = session.exec(
        select(MemberObligation).where(
            MemberObligation.user_id == current_user.id,
            MemberObligation.status.in_(["OVERDUE", "DEFAULTED"])
        )
    ).first() is not None

    settings = session.exec(
        select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group.group_id)
    ).first()

    required_kyc_tier = 0
    if group.type == "MERRY_GO_ROUND":
        rotating_details = session.exec(
            select(RotatingGroupDetails).where(RotatingGroupDetails.group_id == group.group_id)
        ).first()
        if rotating_details and hasattr(rotating_details, "minimum_kyc_tier"):
            required_kyc_tier = getattr(rotating_details, "minimum_kyc_tier", 0) or 0

    requires_guarantor = bool(settings and settings.require_guarantors and request.guarantor_ids)
    requires_admin_approval = bool(settings and (settings.requires_admin_approval or settings.admins_must_approve_new_members))
    minimum_trust = settings.minimum_trust_score if settings else None

    # 4. Invoke the deterministic Rust domain engine
    raw_decision = check_join_rules(
        member_count=group.member_count,
        max_members=group.max_members,
        already_member_or_pending=existing_membership is not None,
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

    # 5. Persist the membership with the server-chosen status
    new_membership = GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=group.group_id,
        user_id=current_user.id,
        role="MEMBER",
        title="Member",
        status=final_status,
        private_settings={}
    )
    session.add(new_membership)

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

        for gid in request.guarantor_ids:
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
            if rotating_details:
                total_liability = rotating_details.contribution_amount * rotating_details.number_of_cycles
                pledge_liability = total_liability // max(1, len(request.guarantor_ids))

        for gid in request.guarantor_ids:
            new_pledge = GuarantorPledge(
                group_id=group.group_id,
                guarantor_user_id=gid,
                borrower_user_id=current_user.id,
                maximum_liability_amount=pledge_liability,
                status="PENDING_CONSENT"
            )
            session.add(new_pledge)

    if final_status == "ACTIVE":
        group.member_count += 1

    # 7. Construct authoritative response payload
    response_payload = {
        "status": "success",
        "message": "Joined successfully!" if final_status == "ACTIVE" else "Join request sent for approval.",
        "membership_status": final_status,
        "group_id": group.group_id
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
            "decision": decision
        },
        actor_user_id=current_user.id
    )

    record_db_idempotency(
        session=session,
        user_id=current_user.id,
        client_request_id=request.client_request_id,
        response_payload=response_payload
    )

    session.commit()

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

    if requires_guarantor and request.guarantor_ids:
        for gid in request.guarantor_ids:
            try:
                guarantor = session.get(User, uuid.UUID(gid))
                if guarantor and guarantor.fcm_token:
                    send_push_notification(
                        token=guarantor.fcm_token,
                        title="Guarantor Request 🤝",
                        body=f"{current_user.full_name} listed you as a guarantor to join '{group.name}'. Tap to review.",
                        data={"type": "GUARANTOR_REQUEST", "group_id": group.group_id}
                    )
            except Exception:
                pass

    return response_payload
