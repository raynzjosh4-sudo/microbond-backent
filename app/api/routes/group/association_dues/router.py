from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select
from typing import Optional, List
import uuid
import time
import logging

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.group import Group, GroupMembership
from app.models.user.user import User
from app.models.group.settings import (
    GroupFinancialSettings, GroupGovernanceSettings,
    GroupCommunicationSettings, GroupVisibilitySettings
)
from app.models.group.investment_association import (
    AssociationDuesConfig,
    AssociationDuesOperationalSettings,
    AssociationMemberDuesStanding,
    AssociationDuesExemption
)
from app.schemas.association_dues_schemas import (
    AssociationDuesGroupCreateRequest,
    UpdateAssociationDuesSettingsRequest,
    PayDuesRequest,
    TriggerTreasurySweepRequest,
    CreateDuesExemptionRequest,
    UpdateDuesExemptionRequest
)
from app.api.routes.group.chat.messages import broadcast_system_message_sync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/groups/association-dues", tags=["Association Dues Groups"])


def _now_ms() -> int:
    return int(time.time() * 1000)


def _get_association(group_id: str, session: Session):
    config = session.exec(
        select(AssociationDuesConfig).where(AssociationDuesConfig.group_id == group_id)
    ).first()
    settings = session.exec(
        select(AssociationDuesOperationalSettings).where(AssociationDuesOperationalSettings.group_id == group_id)
    ).first()
    if not config or not settings:
        raise HTTPException(status_code=404, detail="Association Dues configuration not found for this group.")
    return config, settings


def _require_admin(group_id: str, user: User, session: Session):
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user.id,
            GroupMembership.role == "ADMIN",
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Only the association administrator or treasurer can perform this action.")
    return membership


def _require_member(group_id: str, user: User, session: Session):
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You must be an active member of this association.")
    return membership


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/create", summary="Create a new Association Dues group")
def create_association_dues_group(
    request: AssociationDuesGroupCreateRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new ASSOCIATION_DUES group (Alumni networks, HOAs, unions, professional bodies).
    - Creator must have KYC Tier >= 2 (National ID verified).
    - Initializes AssociationDuesConfig (locked dues and billing schedule).
    - Initializes AssociationDuesOperationalSettings (sweep triggers, late fees, defaulter rules).
    - Adds creator as ADMIN and initializes member dues standing.
    """
    creator = current_user
    now_ms = _now_ms()

    # 1. KYC verification
    if creator.kyc_tier < 2 or getattr(creator, "is_dependent_account", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Creating an Association group requires full Tier 2 National ID (NIN) verification."
        )

    # 2. Identifiers
    new_group_id = str(uuid.uuid4())
    invite_code = str(uuid.uuid4())[:8].upper()

    # 3. Create Group
    new_group = Group(
        group_id=new_group_id,
        name=request.name,
        description=request.description,
        group_image_url=request.group_image_url,
        type="ASSOCIATION_DUES",
        payment_mode="OBLIGATION",
        visibility=request.visibility,
        currency=request.currency,
        created_by_user_id=creator.id,
        invite_code=invite_code,
        member_count=1
    )
    session.add(new_group)

    # 4. Base settings
    session.add(GroupFinancialSettings(group_id=new_group_id))
    session.add(GroupGovernanceSettings(group_id=new_group_id))
    session.add(GroupCommunicationSettings(group_id=new_group_id))
    session.add(GroupVisibilitySettings(group_id=new_group_id))

    # 5. AssociationDuesConfig (Table 1)
    config = AssociationDuesConfig(
        group_id=new_group_id,
        dues_amount=request.dues_amount,
        billing_cycle_days=request.billing_cycle_days,
        billing_start_date=request.billing_start_date,
        treasury_account_id=request.treasury_account_id,
        enable_prorated_dues=request.enable_prorated_dues,
        created_at=now_ms
    )
    session.add(config)

    # 6. AssociationDuesOperationalSettings (Table 2 - defaults)
    op_settings = AssociationDuesOperationalSettings(
        group_id=new_group_id,
        auto_sweep_trigger="END_OF_CYCLE",
        allow_advance_payments=True,
        grace_period_days=7,
        late_fee_amount=0,
        arrears_action="SUSPEND_MEMBERSHIP",
        max_missed_cycles_allowed=3,
        show_defaulters_publicly=False,
        treasury_ledger_visibility="TRANSPARENT",
        allow_installments=True,
        send_arrears_reminders=True,
        arrears_reminder_days_before=3,
        restrict_voting_on_arrears=True,
        restrict_welfare_claims_on_arrears=True,
        current_balance=0,
        total_collected=0,
        total_swept_to_treasury=0,
        active_defaulters_count=0,
        is_active=True,
        updated_at=now_ms
    )
    session.add(op_settings)

    # 7. Creator membership (ADMIN)
    session.add(GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=new_group_id,
        user_id=creator.id,
        role="ADMIN",
        status="ACTIVE",
        joined_at=now_ms
    ))

    # 8. Creator dues standing
    session.add(AssociationMemberDuesStanding(
        group_id=new_group_id,
        user_id=creator.id,
        cycles_paid_ahead=0,
        consecutive_missed_cycles=0,
        outstanding_arrears_balance=0,
        is_in_arrears=False,
        is_suspended=False,
        last_payment_date=None,
        next_due_date=request.billing_start_date,
        updated_at=now_ms
    ))

    try:
        session.commit()
        session.refresh(new_group)
        session.refresh(config)
    except Exception as e:
        session.rollback()
        logger.exception(f"Error creating association dues group: {e}")
        raise HTTPException(status_code=500, detail="Database error creating association dues group.")

    broadcast_system_message_sync(
        group_id=new_group_id,
        message_text=f"{creator.full_name} established the Association '{new_group.name}'.",
        message_type="SYSTEM_EVENT",
        sender_id=str(creator.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Association Dues group created successfully.",
        "data": {
            "group_id": new_group.group_id,
            "invite_code": new_group.invite_code,
            "name": new_group.name,
            "currency": new_group.currency,
            "dues_amount": config.dues_amount,
            "billing_cycle_days": config.billing_cycle_days,
            "billing_start_date": config.billing_start_date,
            "treasury_account_id": config.treasury_account_id
        }
    }


@router.get("/{group_id}/dashboard", summary="View dues cycle, member standing, and treasury health")
def get_association_dashboard(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns full state of the Association:
    - Creation rules (Table 1)
    - Live collection trackers & treasury sweep status (Table 2)
    - Member's personal subscription & dues standing
    """
    member = _require_member(group_id, current_user, session)
    config, settings = _get_association(group_id, session)
    now_ms = _now_ms()

    # Member's standing
    standing = session.exec(
        select(AssociationMemberDuesStanding).where(
            AssociationMemberDuesStanding.group_id == group_id,
            AssociationMemberDuesStanding.user_id == current_user.id
        )
    ).first()

    standing_data = {
        "is_in_arrears": standing.is_in_arrears if standing else False,
        "outstanding_arrears_balance": standing.outstanding_arrears_balance if standing else 0,
        "cycles_paid_ahead": standing.cycles_paid_ahead if standing else 0,
        "is_suspended": standing.is_suspended if standing else False,
        "next_due_date": standing.next_due_date if standing else config.billing_start_date
    }

    # Ledger visibility handling
    settings_dict = settings.model_dump(mode="json")
    if settings.treasury_ledger_visibility == "ADMIN_ONLY" and member.role != "ADMIN":
        settings_dict["current_balance"] = None
        settings_dict["total_collected"] = None
        settings_dict["total_swept_to_treasury"] = None

    days_to_due = max(0, int(((standing_data["next_due_date"]) - now_ms) / (86400 * 1000)))

    return {
        "status": "success",
        "data": {
            "association_config": config.model_dump(mode="json"),
            "operational_settings": settings_dict,
            "my_standing": standing_data,
            "days_to_next_due_date": days_to_due
        }
    }


@router.patch("/{group_id}/settings", summary="Admin updates mutable operational settings")
def update_association_settings(
    group_id: str,
    request: UpdateAssociationDuesSettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Updates mutable operational settings for the Association:
    - auto_sweep_trigger
    - allow_advance_payments
    - grace_period_days
    - late_fee_amount
    - arrears_action
    - max_missed_cycles_allowed
    - show_defaulters_publicly
    - treasury_ledger_visibility
    """
    _require_admin(group_id, current_user, session)
    config, settings = _get_association(group_id, session)

    update_dict = request.dict(exclude_unset=True)
    if not update_dict:
        raise HTTPException(status_code=400, detail="No valid settings provided to update.")

    for field, val in update_dict.items():
        if hasattr(settings, field) and val is not None:
            setattr(settings, field, val)

    settings.updated_at = _now_ms()
    session.add(settings)

    try:
        session.commit()
        session.refresh(settings)
    except Exception as e:
        session.rollback()
        logger.exception(f"Error updating association settings: {e}")
        raise HTTPException(status_code=500, detail="Database error updating settings.")

    return {
        "status": "success",
        "message": "Association settings updated successfully.",
        "data": settings.model_dump(mode="json")
    }


@router.post("/{group_id}/pay-dues", summary="Member pays recurring dues or advance cycles")
def pay_dues(
    group_id: str,
    request: PayDuesRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Member pays dues for one or multiple cycles.
    - Clears arrears and increments prepaid cycles.
    - Updates vault balance.
    - Automatically sweeps to treasury if auto_sweep_trigger is INSTANT.
    """
    _require_member(group_id, current_user, session)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    config, settings = _get_association(group_id, session)
    now_ms = _now_ms()

    if not settings.is_active:
        raise HTTPException(status_code=400, detail="Association billing is currently paused or inactive.")

    if request.cycles_count > 1 and not settings.allow_advance_payments:
        raise HTTPException(status_code=400, detail="Advance multi-cycle payments are not permitted by current settings.")

    total_amount = request.cycles_count * config.dues_amount

    # Update member standing
    standing = session.exec(
        select(AssociationMemberDuesStanding).where(
            AssociationMemberDuesStanding.group_id == group_id,
            AssociationMemberDuesStanding.user_id == current_user.id
        )
    ).first()

    cycle_duration_ms = config.billing_cycle_days * 86400 * 1000

    if not standing:
        standing = AssociationMemberDuesStanding(
            group_id=group_id,
            user_id=current_user.id,
            cycles_paid_ahead=request.cycles_count - 1,
            consecutive_missed_cycles=0,
            outstanding_arrears_balance=0,
            is_in_arrears=False,
            is_suspended=False,
            last_payment_date=now_ms,
            next_due_date=now_ms + (request.cycles_count * cycle_duration_ms),
            updated_at=now_ms
        )
    else:
        standing.outstanding_arrears_balance = 0
        standing.is_in_arrears = False
        standing.consecutive_missed_cycles = 0
        standing.is_suspended = False
        standing.cycles_paid_ahead += (request.cycles_count - 1)
        standing.last_payment_date = now_ms
        base_due = max(now_ms, standing.next_due_date)
        standing.next_due_date = base_due + (request.cycles_count * cycle_duration_ms)
        standing.updated_at = now_ms

    session.add(standing)

    # Update collection counters
    settings.total_collected += total_amount
    settings.current_balance += total_amount

    # Instant auto-sweep check
    was_swept = False
    if settings.auto_sweep_trigger == "INSTANT":
        settings.total_swept_to_treasury += total_amount
        settings.current_balance = max(0, settings.current_balance - total_amount)
        was_swept = True

    settings.updated_at = now_ms
    session.add(settings)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error processing dues payment: {e}")
        raise HTTPException(status_code=500, detail="Database error recording dues payment.")

    sweep_note = " (Auto-swept to external treasury)" if was_swept else ""
    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"💳 Dues Paid: {current_user.full_name} paid {total_amount} {group.currency} for {request.cycles_count} cycle(s){sweep_note}.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": f"Dues payment of {total_amount} {group.currency} successfully recorded.",
        "data": {
            "amount_paid": total_amount,
            "cycles_paid": request.cycles_count,
            "next_due_date": standing.next_due_date,
            "auto_swept_to_treasury": was_swept,
            "vault_balance": settings.current_balance
        }
    }


@router.post("/{group_id}/trigger-sweep", summary="Admin manually sweeps vault balance to association treasury")
def trigger_treasury_sweep(
    group_id: str,
    request: TriggerTreasurySweepRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Admin pushes accumulated dues balance from the vault to the verified association external treasury account.
    """
    _require_admin(group_id, current_user, session)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    config, settings = _get_association(group_id, session)
    now_ms = _now_ms()

    sweep_amount = request.amount if request.amount is not None else settings.current_balance

    if sweep_amount <= 0:
        raise HTTPException(status_code=400, detail="No funds available in the vault to sweep.")

    if settings.current_balance < sweep_amount:
        raise HTTPException(
            status_code=400,
            detail=f"Requested sweep of {sweep_amount} {group.currency} exceeds vault balance of {settings.current_balance} {group.currency}."
        )

    settings.current_balance = max(0, settings.current_balance - sweep_amount)
    settings.total_swept_to_treasury += sweep_amount
    settings.updated_at = now_ms
    session.add(settings)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error sweeping funds: {e}")
        raise HTTPException(status_code=500, detail="Database error executing treasury sweep.")

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"🏛️ Treasury Sweep: {sweep_amount} {group.currency} transferred to Association treasury account.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": f"Successfully swept {sweep_amount} {group.currency} to treasury.",
        "data": {
            "amount_swept": sweep_amount,
            "destination_treasury_account": config.treasury_account_id,
            "remaining_vault_balance": settings.current_balance,
            "total_swept_to_date": settings.total_swept_to_treasury
        }
    }


@router.get("/{group_id}/defaulters", summary="List members currently in arrears")
def list_defaulters(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns list of members in arrears.
    Accessible to admins, or regular members if show_defaulters_publicly is enabled.
    """
    member = _require_member(group_id, current_user, session)
    config, settings = _get_association(group_id, session)

    if member.role != "ADMIN" and not settings.show_defaulters_publicly:
        raise HTTPException(status_code=403, detail="The defaulters ledger is private and only visible to the executive committee.")

    defaulters = session.exec(
        select(AssociationMemberDuesStanding).where(
            AssociationMemberDuesStanding.group_id == group_id,
            AssociationMemberDuesStanding.is_in_arrears == True
        )
    ).all()

    result = []
    for d in defaulters:
        u = session.exec(select(User).where(User.id == d.user_id)).first()
        result.append({
            "user_id": str(d.user_id),
            "full_name": u.full_name if u else "Member",
            "outstanding_arrears_balance": d.outstanding_arrears_balance,
            "consecutive_missed_cycles": d.consecutive_missed_cycles,
            "is_suspended": d.is_suspended,
            "next_due_date": d.next_due_date
        })

    return {
        "status": "success",
        "total_defaulters": len(result),
        "data": result
    }


# ===========================================================================
# FEE EXEMPTIONS (Temporary or Permanent Dues Waivers)
# ===========================================================================

@router.post("/{group_id}/exemptions", summary="Admin: Grant temporary or permanent dues exemption to a member")
def grant_fee_exemption(
    group_id: str,
    request: CreateDuesExemptionRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Grants a dues fee exemption to a member (e.g. students, hardship, elders, honorary members).
    Can be a 100% full waiver or partial discount (discount_percentage).
    """
    _require_admin(group_id, current_user, session)
    now_ms = _now_ms()

    # Verify target user exists and is member of group
    try:
        target_uuid = uuid.UUID(request.user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format. Must be a valid UUID.")

    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == target_uuid,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Target user is not an active member of this association.")

    # Check if there is already an active exemption
    existing = session.exec(
        select(AssociationDuesExemption).where(
            AssociationDuesExemption.group_id == group_id,
            AssociationDuesExemption.user_id == target_uuid,
            AssociationDuesExemption.is_active == True
        )
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Member already has an active fee exemption. Please update or revoke it first.")

    start_date = request.start_date if request.start_date else now_ms
    if request.exemption_type == "TEMPORARY" and not request.end_date:
        raise HTTPException(status_code=400, detail="Temporary exemptions must include an end_date.")

    exemption = AssociationDuesExemption(
        group_id=group_id,
        user_id=target_uuid,
        exemption_type=request.exemption_type,
        reason=request.reason,
        notes=request.notes,
        discount_percentage=request.discount_percentage,
        start_date=start_date,
        end_date=request.end_date,
        is_active=True,
        approved_by=current_user.id,
        created_at=now_ms,
        updated_at=now_ms
    )
    session.add(exemption)

    try:
        session.commit()
        session.refresh(exemption)
    except Exception as e:
        session.rollback()
        logger.exception(f"Error creating fee exemption: {e}")
        raise HTTPException(status_code=500, detail="Database error creating fee exemption.")

    return {
        "status": "success",
        "message": "Fee exemption granted successfully.",
        "data": exemption.model_dump(mode="json")
    }


@router.get("/{group_id}/exemptions", summary="List fee exemptions in this association")
def list_fee_exemptions(
    group_id: str,
    active_only: bool = True,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns list of member fee exemptions.
    Admins see all exemptions; regular members see only their own.
    """
    member = _require_member(group_id, current_user, session)
    query = select(AssociationDuesExemption).where(AssociationDuesExemption.group_id == group_id)

    if member.role != "ADMIN":
        query = query.where(AssociationDuesExemption.user_id == current_user.id)

    if active_only:
        query = query.where(AssociationDuesExemption.is_active == True)

    exemptions = session.exec(query).all()

    result = []
    for ex in exemptions:
        u = session.exec(select(User).where(User.id == ex.user_id)).first()
        result.append({
            "exemption_id": str(ex.id),
            "user_id": str(ex.user_id),
            "member_name": u.full_name if u else "Member",
            "exemption_type": ex.exemption_type,
            "reason": ex.reason,
            "notes": ex.notes,
            "discount_percentage": ex.discount_percentage,
            "start_date": ex.start_date,
            "end_date": ex.end_date,
            "is_active": ex.is_active,
            "created_at": ex.created_at
        })

    return {
        "status": "success",
        "count": len(result),
        "data": result
    }


@router.patch("/{group_id}/exemptions/{exemption_id}", summary="Admin: Update or modify a fee exemption")
def update_fee_exemption(
    group_id: str,
    exemption_id: str,
    request: UpdateDuesExemptionRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Admin updates an existing fee exemption (change duration, notes, discount percentage, or status).
    """
    _require_admin(group_id, current_user, session)
    try:
        ex_uuid = uuid.UUID(exemption_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid exemption_id format.")

    exemption = session.exec(
        select(AssociationDuesExemption).where(
            AssociationDuesExemption.id == ex_uuid,
            AssociationDuesExemption.group_id == group_id
        )
    ).first()
    if not exemption:
        raise HTTPException(status_code=404, detail="Fee exemption not found.")

    update_dict = request.dict(exclude_unset=True)
    for field, val in update_dict.items():
        if hasattr(exemption, field) and val is not None:
            setattr(exemption, field, val)

    exemption.updated_at = _now_ms()
    session.add(exemption)

    try:
        session.commit()
        session.refresh(exemption)
    except Exception as e:
        session.rollback()
        logger.exception(f"Error updating fee exemption: {e}")
        raise HTTPException(status_code=500, detail="Database error updating fee exemption.")

    return {
        "status": "success",
        "message": "Fee exemption updated successfully.",
        "data": exemption.model_dump(mode="json")
    }


@router.delete("/{group_id}/exemptions/{exemption_id}", summary="Admin: Revoke / delete a fee exemption")
def revoke_fee_exemption(
    group_id: str,
    exemption_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Revokes and deletes an exemption, returning the member to standard dues billing.
    """
    _require_admin(group_id, current_user, session)
    try:
        ex_uuid = uuid.UUID(exemption_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid exemption_id format.")

    exemption = session.exec(
        select(AssociationDuesExemption).where(
            AssociationDuesExemption.id == ex_uuid,
            AssociationDuesExemption.group_id == group_id
        )
    ).first()
    if not exemption:
        raise HTTPException(status_code=404, detail="Fee exemption not found.")

    session.delete(exemption)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error deleting fee exemption: {e}")
        raise HTTPException(status_code=500, detail="Database error deleting fee exemption.")

    return {
        "status": "success",
        "message": "Fee exemption revoked successfully."
    }

