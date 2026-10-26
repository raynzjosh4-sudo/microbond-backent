import json
import logging
import uuid
from typing import Optional, List, Dict, Any
from sqlmodel import Session, select
from fastapi import HTTPException

from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.finance import GroupPayout, PayoutSignature
from app.models.group.rotating.rotating_group_details import RotatingGroupDetails
from app.models.group.settings import GroupGovernanceSettings
from app.api.routes.group.chat.messages.helpers.messages_helpers import broadcast_system_message_sync
from app.core.microbond_core import calculate_decayed_quorum
from app.utils.time.now_epoch_ms import now_epoch_ms

logger = logging.getLogger(__name__)


def get_eligible_signers(session: Session, group_id: str) -> List[GroupMembership]:
    """
    Returns active group members authorized to sign payouts (Admin, Treasurer, or explicit is_signer).
    """
    members = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.status == "ACTIVE"
        )
    ).all()

    return [
        m for m in members
        if getattr(m, "is_signer", False) or m.role in ["ADMIN", "TREASURER"]
    ]


def get_required_signatures_count(session: Session, group_id: str) -> int:
    """
    Determines required quorum approvals for a group payout.
    Defaults to 2 signers for Rotating Groups (Admin + Treasurer).
    """
    gov = session.exec(
        select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group_id)
    ).first()

    details = session.exec(
        select(RotatingGroupDetails).where(RotatingGroupDetails.group_id == group_id)
    ).first()

    eligible = get_eligible_signers(session, group_id)
    max_signers = len(eligible)

    if details and getattr(details, "multi_sig_payout_approval", False):
        # Rotating group standard: 2 signers (or all eligible if fewer than 2)
        target = 2
    elif gov:
        target = gov.multi_sig_required_approvals or 2
    else:
        target = 2

    return min(target, max_signers) if max_signers > 0 else 1


def get_payout_multisig_status(
    session: Session,
    group_id: str,
    payout_id: int,
    current_user_id: Optional[uuid.UUID] = None
) -> Dict[str, Any]:
    """
    Returns full multi-signature status, signed progress, signer roster,
    and Time-Locked Quorum Decay (TLQD) calculations.
    """
    payout = session.exec(
        select(GroupPayout).where(
            GroupPayout.id == payout_id,
            GroupPayout.group_id == group_id
        )
    ).first()
    if not payout:
        raise HTTPException(status_code=404, detail="Payout record not found.")

    eligible_signers = get_eligible_signers(session, group_id)
    eligible_user_ids = [m.user_id for m in eligible_signers]

    users = session.exec(select(User).where(User.id.in_(eligible_user_ids))).all() if eligible_user_ids else []
    user_map = {u.id: u for u in users}

    # Fetch all signatures
    signatures = session.exec(
        select(PayoutSignature).where(
            PayoutSignature.payout_id == payout_id,
            PayoutSignature.group_id == group_id
        ).order_by(PayoutSignature.signature_timestamp.asc())
    ).all()

    valid_signatures = [s for s in signatures if s.status == "SIGNED"]
    is_disputed = any(s.status == "DISPUTED" for s in signatures) or payout.status == "FROZEN_DISPUTED"

    # Governance settings & Quorum calculation
    gov = session.exec(
        select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group_id)
    ).first()

    initial_required = get_required_signatures_count(session, group_id)
    decay_hours = gov.quorum_decay_hours if gov else 48
    decay_floor = gov.quorum_decay_minimum_approvals if gov else 1
    enable_decay = gov.enable_quorum_decay if gov else True

    now_ms = now_epoch_ms()
    created_at_ms = payout.created_at or now_ms

    params = {
        "initial_required_approvals": initial_required,
        "minimum_decay_floor_approvals": decay_floor,
        "decay_interval_hours": decay_hours,
        "enable_decay": enable_decay,
    }

    eval_json = calculate_decayed_quorum(
        params=params,
        request_created_at_ms=created_at_ms,
        current_time_ms=now_ms,
        current_approvals=len(valid_signatures)
    )
    eval_res = json.loads(eval_json)

    effective_required = eval_res.get("current_required_approvals", initial_required)
    is_quorum_reached = eval_res.get("is_approved", len(valid_signatures) >= effective_required)

    elapsed_ms = max(0, now_ms - created_at_ms)
    elapsed_hours = int(elapsed_ms // (1000 * 60 * 60))
    hours_until_next = max(0, decay_hours - (elapsed_hours % decay_hours))

    # Current user context
    has_user_signed = False
    can_user_sign = False
    if current_user_id:
        has_user_signed = any(s.signer_user_id == current_user_id and s.status == "SIGNED" for s in signatures)
        is_eligible_signer = any(m.user_id == current_user_id for m in eligible_signers)
        can_user_sign = is_eligible_signer and not has_user_signed and payout.status in ["PENDING", "PENDING_MULTISIG_APPROVAL"]

    # Signer Roster Presentation
    signer_roster = []
    signed_user_ids = {s.signer_user_id for s in valid_signatures}

    for m in eligible_signers:
        u = user_map.get(m.user_id)
        matching_sig = next((s for s in valid_signatures if s.signer_user_id == m.user_id), None)
        signer_roster.append({
            "user_id": str(m.user_id),
            "full_name": u.full_name if u else "Signer",
            "role": m.role,
            "has_signed": matching_sig is not None,
            "signed_at": matching_sig.signature_timestamp if matching_sig else None,
            "device_fingerprint": matching_sig.device_fingerprint if matching_sig else None,
            "avatar_url": getattr(u, "profile_picture_url", None) if u else None
        })

    return {
        "payout_id": payout.id,
        "group_id": group_id,
        "cycle_number": payout.cycle_number,
        "amount_expected": payout.amount_expected,
        "amount_received": payout.amount_received,
        "payout_status": payout.status,
        "hold_reason": payout.hold_reason,
        "is_disputed": is_disputed,
        "collected_signatures_count": len(valid_signatures),
        "required_signatures": effective_required,
        "initial_required_signatures": initial_required,
        "is_quorum_reached": is_quorum_reached,
        "has_current_user_signed": has_user_signed,
        "can_current_user_sign": can_user_sign,
        "signer_roster": signer_roster,
        "tlqd": {
            "decay_enabled": enable_decay,
            "decay_applied": eval_res.get("decay_applied", False),
            "elapsed_hours": elapsed_hours,
            "decay_interval_hours": decay_hours,
            "hours_until_next_decay": hours_until_next,
            "decay_floor": decay_floor
        }
    }


def sign_payout(
    session: Session,
    group_id: str,
    payout_id: int,
    user: User,
    pin: Optional[str] = None,
    device_fingerprint: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes a multi-sig approval signature with pessimistic idempotency.
    Advances status to APPROVED_FOR_DISBURSEMENT when quorum is satisfied.
    """
    # 1. Signer authorization check
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()

    if not membership or (not getattr(membership, "is_signer", False) and membership.role not in ["ADMIN", "TREASURER"]):
        raise HTTPException(
            status_code=403,
            detail="Only authorized group signers (Admin or Treasurer) can sign payouts."
        )

    # 2. Payout validation
    payout = session.exec(
        select(GroupPayout).where(
            GroupPayout.id == payout_id,
            GroupPayout.group_id == group_id
        )
    ).first()

    if not payout:
        raise HTTPException(status_code=404, detail="Payout record not found.")

    if payout.status == "FROZEN_DISPUTED":
        raise HTTPException(status_code=400, detail="Cannot sign: Payout is currently frozen due to an active dispute.")

    if payout.status in ["COMPLETED", "APPROVED_FOR_DISBURSEMENT", "PROCESSING"]:
        raise HTTPException(status_code=400, detail=f"Payout cannot be signed: current status is {payout.status}.")

    # 3. Pessimistic Idempotency: Has user already signed?
    existing_signature = session.exec(
        select(PayoutSignature).where(
            PayoutSignature.payout_id == payout_id,
            PayoutSignature.signer_user_id == user.id,
            PayoutSignature.status == "SIGNED"
        )
    ).first()

    if existing_signature:
        raise HTTPException(status_code=400, detail="You have already signed this payout.")

    # 4. Insert signature record
    now_ms = now_epoch_ms()
    sig = PayoutSignature(
        group_id=group_id,
        payout_id=payout_id,
        signer_user_id=user.id,
        signer_role=membership.role or "SIGNER",
        status="SIGNED",
        pin_verified=True,
        device_fingerprint=device_fingerprint or "ANDROID_CLIENT",
        signature_timestamp=now_ms
    )
    session.add(sig)
    session.flush()

    # 5. Count collected signatures
    signatures = session.exec(
        select(PayoutSignature).where(
            PayoutSignature.payout_id == payout_id,
            PayoutSignature.status == "SIGNED"
        )
    ).all()
    collected_count = len(signatures)

    # 6. Evaluate quorum
    required_count = get_required_signatures_count(session, group_id)
    quorum_reached = collected_count >= required_count

    if quorum_reached:
        payout.status = "APPROVED_FOR_DISBURSEMENT"
        payout.hold_reason = f"Quorum reached ({collected_count}/{required_count} signatures). Co-signed by {membership.role} {user.full_name}."
    else:
        payout.status = "PENDING_MULTISIG_APPROVAL"
        payout.hold_reason = f"Awaiting signatures ({collected_count}/{required_count} collected)."

    session.add(payout)
    session.commit()
    session.refresh(payout)

    logger.info(
        f"[MULTISIG] User {user.id} ({membership.role}) signed payout {payout_id}. "
        f"Progress: {collected_count}/{required_count}. Quorum reached: {quorum_reached}."
    )

    return {
        "status": "success",
        "message": f"Signature recorded. {collected_count} of {required_count} signatures collected.",
        "data": {
            "payout_id": payout.id,
            "payout_status": payout.status,
            "collected_signatures": collected_count,
            "required_signatures": required_count,
            "is_quorum_reached": quorum_reached
        }
    }


def dispute_payout(
    session: Session,
    group_id: str,
    payout_id: int,
    user: User,
    reason: str
) -> Dict[str, Any]:
    """
    Freezes a payout due to suspected fraud or discrepancy, halting disbursement and TLQD decay.
    """
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()

    if not membership or (not getattr(membership, "is_signer", False) and membership.role not in ["ADMIN", "TREASURER"]):
        raise HTTPException(
            status_code=403,
            detail="Only authorized group signers can dispute/freeze payouts."
        )

    payout = session.exec(
        select(GroupPayout).where(
            GroupPayout.id == payout_id,
            GroupPayout.group_id == group_id
        )
    ).first()

    if not payout:
        raise HTTPException(status_code=404, detail="Payout record not found.")

    if payout.status == "COMPLETED":
        raise HTTPException(status_code=400, detail="Cannot dispute: Payout has already been disbursed.")

    now_ms = now_epoch_ms()
    sig = PayoutSignature(
        group_id=group_id,
        payout_id=payout_id,
        signer_user_id=user.id,
        signer_role=membership.role or "SIGNER",
        status="DISPUTED",
        notes=reason,
        signature_timestamp=now_ms
    )
    session.add(sig)

    payout.status = "FROZEN_DISPUTED"
    payout.hold_reason = f"Frozen by {membership.role} {user.full_name}: {reason}"
    session.add(payout)
    session.commit()
    session.refresh(payout)

    # Broadcast system message into group chat
    try:
        broadcast_system_message_sync(
            group_id=group_id,
            message_text=f"⚠️ Payout for Cycle {payout.cycle_number} has been frozen by {membership.role} {user.full_name}.\nReason: {reason}",
            message_type="SYSTEM_ALERT"
        )
    except Exception as ex:
        logger.warning(f"[MULTISIG] Chat dispute broadcast warning: {ex}")

    return {
        "status": "success",
        "message": "Payout has been frozen due to an active dispute.",
        "data": {
            "payout_id": payout.id,
            "payout_status": payout.status,
            "hold_reason": payout.hold_reason
        }
    }
