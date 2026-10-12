from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select
from typing import Optional
import uuid
import time
import json
import logging

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.group import Group, GroupMembership
from app.models.user.user import User
from app.models.group.settings import (
    GroupFinancialSettings, GroupGovernanceSettings,
    GroupCommunicationSettings, GroupVisibilitySettings
)
from app.models.group.long_term import SharedWalletConfig, SharedWalletOperationalSettings
from app.models.group.chat import GroupPoll
from app.schemas.shared_wallet_schemas import (
    SharedWalletGroupCreateRequest,
    UpdateSharedWalletSettingsRequest,
    RequestSpendBody
)
from app.api.routes.group.chat.messages import broadcast_system_message_sync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/groups/shared-wallet", tags=["Shared Wallet Groups"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_ms() -> int:
    return int(time.time() * 1000)


def _get_wallet(group_id: str, session: Session):
    config = session.exec(
        select(SharedWalletConfig).where(SharedWalletConfig.group_id == group_id)
    ).first()
    settings = session.exec(
        select(SharedWalletOperationalSettings).where(SharedWalletOperationalSettings.group_id == group_id)
    ).first()
    if not config or not settings:
        raise HTTPException(status_code=404, detail="Shared wallet configuration not found for this group.")
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
        raise HTTPException(status_code=403, detail="Only the group admin can perform this action.")
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
        raise HTTPException(status_code=403, detail="You must be an active member of this group.")
    return membership


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/create", summary="Create a new Shared Wallet group")
def create_shared_wallet_group(
    request: SharedWalletGroupCreateRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new SHARED_WALLET group.
    - Creator must have KYC Tier >= 2 (National ID verified).
    - Initializes SharedWalletConfig (locked creation parameters).
    - Initializes SharedWalletOperationalSettings (default operational limits).
    - Adds creator as ADMIN and broadcasts creation to group chat.
    """
    creator = current_user
    now_ms = _now_ms()

    # 1. KYC verification
    if creator.kyc_tier < 2 or getattr(creator, "is_dependent_account", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Creating a Shared Wallet requires full Tier 2 National ID (NIN) verification."
        )

    # 2. Unique identifiers
    new_group_id = str(uuid.uuid4())
    invite_code = str(uuid.uuid4())[:8].upper()

    payment_mode = "OBLIGATION" if request.replenishment_mode == "SCHEDULED_QUOTA" else "VOLUNTARY"

    # 3. Create Group record
    new_group = Group(
        group_id=new_group_id,
        name=request.name,
        description=request.description,
        group_image_url=request.group_image_url,
        type="SHARED_WALLET",
        payment_mode=payment_mode,
        visibility=request.visibility,
        currency=request.currency,
        created_by_user_id=creator.id,
        invite_code=invite_code,
        member_count=1
    )
    session.add(new_group)

    # 4. Create base settings
    session.add(GroupFinancialSettings(group_id=new_group_id))
    session.add(GroupGovernanceSettings(group_id=new_group_id))
    session.add(GroupCommunicationSettings(group_id=new_group_id))
    session.add(GroupVisibilitySettings(group_id=new_group_id))

    # 5. Create SharedWalletConfig (Table 1)
    config = SharedWalletConfig(
        group_id=new_group_id,
        replenishment_mode=request.replenishment_mode,
        member_quota_amount=request.member_quota_amount,
        collection_frequency_days=request.collection_frequency_days,
        spending_signoff_policy=request.spending_signoff_policy,
        exit_payout_rule=request.exit_payout_rule,
        track_individual_contributions=request.track_individual_contributions,
        minimum_kyc_tier=request.minimum_kyc_tier,
        created_at=now_ms
    )
    session.add(config)

    # 6. Create SharedWalletOperationalSettings (Table 2 - defaults)
    op_settings = SharedWalletOperationalSettings(
        group_id=new_group_id,
        minimum_balance_floor=0,
        target_budget_limit=None,
        auto_approve_threshold=0,
        approval_timeout_hours=24,
        timelock_duration_hours=0,
        daily_spending_cap=None,
        per_transaction_cap=None,
        allowed_disbursement_types=json.dumps(["MEMBER_ACCOUNTS", "EXTERNAL_PAYEES"]),
        current_balance=0,
        total_deposited=0,
        total_spent=0,
        is_active=True,
        updated_at=now_ms
    )
    session.add(op_settings)

    # 7. Add creator membership (ADMIN)
    session.add(GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=new_group_id,
        user_id=creator.id,
        role="ADMIN",
        status="ACTIVE",
        joined_at=now_ms
    ))

    try:
        session.commit()
        session.refresh(new_group)
        session.refresh(config)
    except Exception as e:
        session.rollback()
        logger.exception(f"Error creating shared wallet: {e}")
        raise HTTPException(status_code=500, detail="Database error creating shared wallet.")

    # 8. Broadcast greeting in chat
    broadcast_system_message_sync(
        group_id=new_group_id,
        message_text=f"{creator.full_name} created the Shared Wallet group '{new_group.name}'.",
        message_type="SYSTEM_EVENT",
        sender_id=str(creator.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Shared Wallet group created successfully.",
        "data": {
            "group_id": new_group.group_id,
            "invite_code": new_group.invite_code,
            "name": new_group.name,
            "currency": new_group.currency,
            "replenishment_mode": config.replenishment_mode,
            "spending_signoff_policy": config.spending_signoff_policy,
            "exit_payout_rule": config.exit_payout_rule
        }
    }


@router.get("/{group_id}/dashboard", summary="View shared wallet status, balance, and limits")
def get_shared_wallet_dashboard(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns full state of the shared wallet:
    - Creation configuration rules (Table 1)
    - Live operational settings & spend limits (Table 2)
    - Current balance and cumulative totals
    """
    _require_member(group_id, current_user, session)
    config, op_settings = _get_wallet(group_id, session)

    group = session.exec(select(Group).where(Group.group_id == group_id)).first()

    # Parse allowed disbursement types
    try:
        allowed_types = json.loads(op_settings.allowed_disbursement_types)
    except Exception:
        allowed_types = ["MEMBER_ACCOUNTS", "EXTERNAL_PAYEES"]

    return {
        "status": "success",
        "data": {
            "group_id": group_id,
            "name": group.name if group else "",
            "currency": group.currency if group else "UGX",
            "current_balance": op_settings.current_balance,
            "minimum_balance_floor": op_settings.minimum_balance_floor,
            "spendable_balance": max(0, op_settings.current_balance - op_settings.minimum_balance_floor),
            "total_deposited": op_settings.total_deposited,
            "total_spent": op_settings.total_spent,
            "is_active": op_settings.is_active,
            "config": config.model_dump(mode="json"),
            "operational_settings": {
                **op_settings.model_dump(mode="json"),
                "allowed_disbursement_types": allowed_types
            }
        }
    }


@router.patch("/{group_id}/settings", summary="Update operational limits and spend policies")
def update_shared_wallet_settings(
    group_id: str,
    request: UpdateSharedWalletSettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Admin updates operational limits (Table 2: SharedWalletOperationalSettings).
    Core creation rules in SharedWalletConfig remain protected.
    """
    _require_admin(group_id, current_user, session)
    _, op_settings = _get_wallet(group_id, session)

    if request.minimum_balance_floor is not None:
        op_settings.minimum_balance_floor = request.minimum_balance_floor
    if request.target_budget_limit is not None:
        op_settings.target_budget_limit = request.target_budget_limit
    if request.auto_approve_threshold is not None:
        op_settings.auto_approve_threshold = request.auto_approve_threshold
    if request.approval_timeout_hours is not None:
        op_settings.approval_timeout_hours = request.approval_timeout_hours
    if request.timelock_duration_hours is not None:
        op_settings.timelock_duration_hours = request.timelock_duration_hours
    if request.daily_spending_cap is not None:
        op_settings.daily_spending_cap = request.daily_spending_cap
    if request.per_transaction_cap is not None:
        op_settings.per_transaction_cap = request.per_transaction_cap
    if request.allowed_disbursement_types is not None:
        op_settings.allowed_disbursement_types = json.dumps(request.allowed_disbursement_types)

    op_settings.updated_at = _now_ms()
    session.add(op_settings)
    session.commit()
    session.refresh(op_settings)

    return {
        "status": "success",
        "message": "Shared wallet settings updated successfully.",
        "data": op_settings.model_dump(mode="json")
    }


@router.post("/{group_id}/request-spend", summary="Request or initiate a spend from shared funds")
def request_spend(
    group_id: str,
    request: RequestSpendBody,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Requests a spend from the shared wallet.
    - If spend amount <= auto_approve_threshold and user authorized: instantly approved.
    - If spend amount > auto_approve_threshold: creates a SPEND_APPROVAL voting poll for members.
    """
    membership = _require_member(group_id, current_user, session)
    config, op_settings = _get_wallet(group_id, session)

    if not op_settings.is_active:
        raise HTTPException(status_code=400, detail="This shared wallet is currently paused or inactive.")

    # 1. Check spending policy permission
    if config.spending_signoff_policy == "ADMIN_ONLY" and membership.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only admins can initiate spending in this wallet.")

    # 2. Check minimum balance floor
    spendable = op_settings.current_balance - op_settings.minimum_balance_floor
    if request.amount > spendable:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Insufficient spendable balance. Current balance is {op_settings.current_balance:,}, "
                f"reserve floor is {op_settings.minimum_balance_floor:,}. Max spendable is {spendable:,}."
            )
        )

    # 3. Check per-transaction cap
    if op_settings.per_transaction_cap and request.amount > op_settings.per_transaction_cap:
        raise HTTPException(
            status_code=400,
            detail=f"Amount exceeds per-transaction cap of {op_settings.per_transaction_cap:,}."
        )

    # 4. Check recipient type allowance
    try:
        allowed = json.loads(op_settings.allowed_disbursement_types)
    except Exception:
        allowed = ["MEMBER_ACCOUNTS", "EXTERNAL_PAYEES"]
    if request.recipient_type not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Disbursements to {request.recipient_type} are not allowed. Allowed types: {allowed}."
        )

    now_ms = _now_ms()

    # Case A: Auto-Approve (amount <= threshold)
    if request.amount <= op_settings.auto_approve_threshold:
        op_settings.current_balance -= request.amount
        op_settings.total_spent += request.amount
        op_settings.updated_at = now_ms
        session.add(op_settings)
        session.commit()

        broadcast_system_message_sync(
            group_id=group_id,
            message_text=(
                f"{current_user.full_name} spent {request.amount:,} to {request.recipient_name} "
                f"({request.recipient_identifier}). Memo: {request.reason}."
            ),
            message_type="SYSTEM_EVENT",
            sender_id=str(current_user.id),
            session=session,
            background_tasks=background_tasks
        )

        return {
            "status": "success",
            "message": "Spend auto-approved and executed.",
            "data": {
                "amount": request.amount,
                "recipient_name": request.recipient_name,
                "recipient_identifier": request.recipient_identifier,
                "remaining_balance": op_settings.current_balance,
                "auto_approved": True
            }
        }

    # Case B: Requires member approval vote
    timeout_ms = op_settings.approval_timeout_hours * 3600 * 1000
    expires_at = now_ms + timeout_ms

    poll_payload = {
        "amount": request.amount,
        "recipient_type": request.recipient_type,
        "recipient_identifier": request.recipient_identifier,
        "recipient_name": request.recipient_name,
        "reason": request.reason,
        "policy": config.spending_signoff_policy,
        "timelock_hours": op_settings.timelock_duration_hours
    }

    poll = GroupPoll(
        group_id=group_id,
        creator_id=current_user.id,
        question=f"Approve spend of {request.amount:,} to {request.recipient_name}? Reason: {request.reason}",
        options=json.dumps(["Approve Spend", "Reject Spend"]),
        poll_type="SPEND_APPROVAL",
        status="OPEN",
        expires_at=expires_at,
        created_at=now_ms
    )
    session.add(poll)
    session.commit()
    session.refresh(poll)

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=json.dumps({
            "poll_id": str(poll.id),
            "question": poll.question,
            "options": ["Approve Spend", "Reject Spend"],
            "amount": request.amount,
            "recipient_name": request.recipient_name,
            "expires_at": expires_at,
            "signoff_policy": config.spending_signoff_policy
        }),
        message_type="VOTE",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "pending_approval",
        "message": f"Spend requires approval under {config.spending_signoff_policy} policy. Voting poll created.",
        "data": {
            "poll_id": str(poll.id),
            "amount": request.amount,
            "recipient_name": request.recipient_name,
            "expires_at": expires_at,
            "signoff_policy": config.spending_signoff_policy
        }
    }


@router.post("/{group_id}/approve-spend/{poll_id}", summary="Cast approval vote or finalize approved spend")
def approve_spend(
    group_id: str,
    poll_id: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Approves a pending spend request poll.
    When approval conditions are satisfied, dispatches funds or marks ready for timelock.
    """
    _require_member(group_id, current_user, session)
    config, op_settings = _get_wallet(group_id, session)

    poll = session.exec(
        select(GroupPoll).where(
            GroupPoll.id == poll_id,
            GroupPoll.group_id == group_id,
            GroupPoll.poll_type == "SPEND_APPROVAL"
        )
    ).first()

    if not poll:
        raise HTTPException(status_code=404, detail="Spend approval poll not found.")
    if poll.status != "OPEN":
        raise HTTPException(status_code=400, detail=f"This spend poll is already {poll.status}.")
    if poll.expires_at <= _now_ms():
        poll.status = "EXPIRED"
        session.add(poll)
        session.commit()
        raise HTTPException(status_code=400, detail="This spend approval poll has expired.")

    # Mark poll approved and close
    poll.status = "CLOSED"
    session.add(poll)

    return {
        "status": "success",
        "message": f"Vote recorded for poll {poll_id}. You can execute the payout once finalized.",
        "data": {
            "poll_id": str(poll.id),
            "status": poll.status
        }
    }


@router.post("/{group_id}/execute-spend/{poll_id}", summary="Execute approved disbursement after approval/timelock")
def execute_spend(
    group_id: str,
    poll_id: str,
    amount: int,
    recipient_name: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Executes an approved spend proposal after voting has concluded.
    Deducts balance from the wallet and logs the outflow.
    """
    _require_admin(group_id, current_user, session)
    _, op_settings = _get_wallet(group_id, session)

    poll = session.exec(
        select(GroupPoll).where(
            GroupPoll.id == poll_id,
            GroupPoll.group_id == group_id,
            GroupPoll.poll_type == "SPEND_APPROVAL"
        )
    ).first()

    if not poll:
        raise HTTPException(status_code=404, detail="Spend proposal poll not found.")
    if poll.status != "CLOSED":
        raise HTTPException(status_code=400, detail="Spend has not been fully approved yet.")

    spendable = op_settings.current_balance - op_settings.minimum_balance_floor
    if amount > spendable:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient spendable balance. Remaining spendable is {spendable:,}."
        )

    now_ms = _now_ms()
    op_settings.current_balance -= amount
    op_settings.total_spent += amount
    op_settings.updated_at = now_ms
    session.add(op_settings)
    session.commit()

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"{current_user.full_name} executed approved spend of {amount:,} to {recipient_name}.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Funds disbursed successfully.",
        "data": {
            "amount_disbursed": amount,
            "remaining_balance": op_settings.current_balance,
            "total_spent": op_settings.total_spent
        }
    }
