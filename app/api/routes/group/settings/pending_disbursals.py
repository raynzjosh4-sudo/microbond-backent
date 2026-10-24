import time
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.finance import GroupPayout
from app.models.group.settings import GroupFinancialSettings, GroupVisibilitySettings
from app.services.group.payout_queue_service import is_payout_queue_full
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api/v1/groups", tags=["Pending Disbursals Queue Settings"])


class UpdatePendingDisbursalsRequest(BaseModel):
    max_pending_payouts: Optional[int] = Field(
        default=None,
        ge=1,
        le=10,
        description="Maximum allowable unresolved pending payouts before auto-freezing cycle progression (circuit breaker)"
    )
    vis_pending_payout_queue: Optional[bool] = Field(
        default=None,
        description="Whether regular group members can see the pending payout queue and counter"
    )


class PendingPayoutItem(BaseModel):
    id: int
    user_id: str
    recipient_name: str
    recipient_phone: str
    recipient_avatar: Optional[str] = None
    cycle_number: int
    amount_expected: int
    amount_expected_formatted: str
    status: str  # PENDING, PROCESSING, ON_HOLD
    hold_reason: Optional[str] = None
    payout_date: int
    payout_date_formatted: str


@router.get(
    "/{group_id}/settings/pending-disbursals",
    summary="Get Pending Disbursals Queue and Circuit Breaker Status",
    description="Returns the active queue of pending or held payouts, circuit breaker threshold, and member visibility."
)
def get_pending_disbursals(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You must be an active member of this group.")

    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    is_admin = membership.role in ["ADMIN", "TREASURER"]

    # Visibility check
    vis = session.exec(select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)).first()
    if not vis:
        vis = GroupVisibilitySettings(group_id=group_id)
        session.add(vis)
        session.commit()
        session.refresh(vis)

    if not is_admin and not vis.vis_pending_payout_queue:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The pending disbursals queue is restricted to group administrators."
        )

    fin_settings = session.exec(
        select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group_id)
    ).first()
    if not fin_settings:
        fin_settings = GroupFinancialSettings(group_id=group_id)
        session.add(fin_settings)
        session.commit()
        session.refresh(fin_settings)

    # Fetch queued payouts (PENDING, PROCESSING, ON_HOLD)
    queued_payouts_rows = session.exec(
        select(GroupPayout, User)
        .join(User, GroupPayout.user_id == User.id)
        .where(
            GroupPayout.group_id == group_id,
            GroupPayout.status.in_(["PENDING", "PROCESSING", "ON_HOLD"])
        )
        .order_by(GroupPayout.cycle_number.asc(), GroupPayout.payout_date.asc())
    ).all()

    currency = group.currency or "UGX"

    items: List[PendingPayoutItem] = []
    for p, u in queued_payouts_rows:
        date_str = time.strftime("%b %d, %Y", time.gmtime(p.payout_date / 1000.0)) if p.payout_date else "Scheduled"
        items.append(
            PendingPayoutItem(
                id=p.id,
                user_id=str(u.id),
                recipient_name=u.full_name or "Group Member",
                recipient_phone=u.phone_number or "",
                recipient_avatar=u.profile_picture_url,
                cycle_number=p.cycle_number,
                amount_expected=p.amount_expected,
                amount_expected_formatted=f"{currency} {p.amount_expected:,.0f}",
                status=p.status,
                hold_reason=p.hold_reason,
                payout_date=p.payout_date,
                payout_date_formatted=date_str
            )
        )

    queue_full = is_payout_queue_full(session, group_id)
    max_limit = fin_settings.max_pending_payouts or 2

    return {
        "status": "success",
        "data": {
            "group_id": group_id,
            "group_name": getattr(group, "name", "Savings Group"),
            "currency": currency,
            "pending_disbursals_count": len(items),
            "max_pending_payouts": max_limit,
            "is_queue_full": queue_full,
            "circuit_breaker_active": queue_full,
            "circuit_breaker_status": "TRIGGERED (Group Frozen)" if queue_full else "NORMAL (Safe)",
            "vis_pending_payout_queue": vis.vis_pending_payout_queue,
            "payouts": [item.dict() for item in items]
        }
    }


@router.patch(
    "/{group_id}/settings/pending-disbursals",
    summary="Update Pending Disbursals Queue Threshold & Visibility",
    description="Updates maximum allowable queued payouts and regular member visibility."
)
def update_pending_disbursals(
    group_id: str,
    request: UpdatePendingDisbursalsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership or membership.role not in ["ADMIN", "TREASURER"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only group administrators or treasurers can update pending disbursal limits."
        )

    fin_settings = session.exec(
        select(GroupFinancialSettings).where(GroupFinancialSettings.group_id == group_id)
    ).first()
    if not fin_settings:
        fin_settings = GroupFinancialSettings(group_id=group_id)

    vis = session.exec(select(GroupVisibilitySettings).where(GroupVisibilitySettings.group_id == group_id)).first()
    if not vis:
        vis = GroupVisibilitySettings(group_id=group_id)

    changes = []
    if request.max_pending_payouts is not None:
        fin_settings.max_pending_payouts = request.max_pending_payouts
        changes.append(f"max_pending_payouts={request.max_pending_payouts}")

    if request.vis_pending_payout_queue is not None:
        vis.vis_pending_payout_queue = request.vis_pending_payout_queue
        changes.append(f"vis_pending_payout_queue={request.vis_pending_payout_queue}")

    session.add(fin_settings)
    session.add(vis)
    session.commit()
    session.refresh(fin_settings)
    session.refresh(vis)

    if changes:
        AuditService.record_event(
            session=session,
            group_id=group_id,
            user_id=current_user.id,
            action="PENDING_DISBURSALS_QUEUE_UPDATED",
            description=f"Admin {current_user.full_name} updated pending queue settings: {', '.join(changes)}"
        )

    return get_pending_disbursals(group_id=group_id, session=session, current_user=current_user)
