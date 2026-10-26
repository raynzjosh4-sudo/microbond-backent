import json
import logging
from typing import Optional, Dict, Any
from sqlmodel import Session, select
from datetime import datetime, timezone
from fastapi import BackgroundTasks

from app.models.group.finance import GroupPayout, PayoutSignature
from app.models.group.settings import GroupGovernanceSettings
from app.models.group.rotating.rotating_group_details import RotatingGroupDetails
from app.models.group.group import Group
from app.api.routes.group.chat.messages.helpers.messages_helpers import broadcast_system_message_sync
from app.core.microbond_core import calculate_decayed_quorum
from app.utils.time.now_epoch_ms import now_epoch_ms

logger = logging.getLogger(__name__)


def process_time_locked_quorum_decay(
    session: Session,
    background_tasks: Optional[BackgroundTasks] = None,
    now_ms_override: Optional[int] = None
) -> Dict[str, Any]:
    """
    Cron Job: Runs every hour.
    Scans pending multi-signature payout requests (status == 'PENDING_MULTISIG_APPROVAL').
    Applies Time-Locked Quorum Decay (TLQD) to mathematically lower the required
    approvals based on elapsed time, resolving 'hostage signer' deadlocks.
    """
    now_ms = now_ms_override if now_ms_override is not None else now_epoch_ms()

    pending_payouts = session.exec(
        select(GroupPayout).where(
            GroupPayout.status == "PENDING_MULTISIG_APPROVAL"
        )
    ).all()

    decayed_payouts = []

    for payout in pending_payouts:
        group_id = payout.group_id
        
        gov_settings = session.exec(
            select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group_id)
        ).first()

        rotating_details = session.exec(
            select(RotatingGroupDetails).where(RotatingGroupDetails.group_id == group_id)
        ).first()

        # Quorum Decay Configuration
        enable_decay = gov_settings.enable_quorum_decay if gov_settings else True
        if not enable_decay:
            continue

        decay_interval_hours = gov_settings.quorum_decay_hours if gov_settings else 48
        decay_floor = gov_settings.quorum_decay_minimum_approvals if gov_settings else 1
        initial_required = 2
        if gov_settings and gov_settings.multi_sig_required_approvals:
            initial_required = gov_settings.multi_sig_required_approvals

        # Query collected signatures for this payout
        signatures = session.exec(
            select(PayoutSignature).where(
                PayoutSignature.payout_id == payout.id,
                PayoutSignature.status == "SIGNED"
            )
        ).all()
        current_approvals = len(signatures)

        created_at_ms = payout.created_at or now_ms

        params = {
            "initial_required_approvals": initial_required,
            "minimum_decay_floor_approvals": decay_floor,
            "decay_interval_hours": decay_interval_hours,
            "enable_decay": enable_decay,
        }

        eval_json = calculate_decayed_quorum(
            params=params,
            request_created_at_ms=created_at_ms,
            current_time_ms=now_ms,
            current_approvals=current_approvals
        )
        eval_res = json.loads(eval_json)

        if eval_res.get("is_approved") and payout.status == "PENDING_MULTISIG_APPROVAL":
            current_quorum = eval_res.get("current_required_approvals", decay_floor)
            original_quorum = eval_res.get("initial_approvals", initial_required)

            # 1. Update payout status to APPROVED_BY_DECAY
            payout.status = "APPROVED_BY_DECAY"
            payout.hold_reason = (
                f"Approved via Time-Locked Quorum Decay after {decay_interval_hours}h signer inactivity. "
                f"Quorum decayed from {original_quorum} to {current_quorum} (collected: {current_approvals})."
            )
            session.add(payout)
            decayed_payouts.append(payout.id)

            logger.info(
                f"[TLQD] Triggered for Group {group_id}. Payout {payout.id} cleared via Quorum Decay "
                f"with {current_approvals} approvals (threshold decayed from {original_quorum} to {current_quorum})."
            )

            # 2. Broadcast System Chat Message to the Group
            try:
                broadcast_system_message_sync(
                    group_id=group_id,
                    message_text=(
                        f"🛡️ Time-Locked Quorum Decay Activated\n"
                        f"Cycle {payout.cycle_number} payout cleared after {decay_interval_hours}h offline signer inactivity. "
                        f"Required signatures decayed from {original_quorum} to {current_quorum}."
                    ),
                    message_type="SYSTEM_EVENT",
                    session=session,
                    background_tasks=background_tasks
                )
            except Exception as ex:
                logger.warning(f"[TLQD] System chat broadcast warning: {ex}")

    if decayed_payouts:
        session.commit()

    return {
        "status": "success",
        "processed_decays_count": len(decayed_payouts),
        "decayed_payout_ids": decayed_payouts
    }
