from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import time
import uuid

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.user.kyc import KycProfile, KycDocument
from app.models.user.security_email import UserSecurityEmail
from app.models.user.userpaymentmethod.payment_method import UserPaymentMethod
from app.models.user.userpayoutaccount.payout_destination import UserPayoutDestination
from app.models.group.group import Group, GroupMembership
from app.models.group.finance import (
    MemberObligation,
    GroupPayout,
    GroupPenalty,
    GuarantorPledge,
    TurnSwapRequest,
)
from app.models.group.investment_association import (
    InvestmentClubMemberShare,
    InvestmentClubLoan,
    AssociationMemberDuesStanding,
)
from app.models.group.long_term import TargetSavingsGroupDetails
from app.services.websocket_manager import ws_manager
from app.services.communication.email_service import EmailNotificationService

router = APIRouter(prefix="/api/v1/users", tags=["Account Management & GDPR"])


class DeleteAccountRequest(BaseModel):
    confirmation: str = Field(..., description="Must type 'DELETE MY ACCOUNT' to confirm")
    reason: Optional[str] = Field(default=None, description="Optional exit survey / reason for closure")
    app_pin: Optional[str] = Field(default=None, description="Required if user has set an App PIN")


# ---------------------------------------------------------------------------
# GDPR: Data Export
# ---------------------------------------------------------------------------

@router.get("/me/export-gdpr", summary="GDPR: Export Complete Personal Data Archive")
def export_user_data(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    GDPR Article 20: Right to Data Portability.
    Exports all personal, identity, device, and group participation data held about the user in JSON.
    """
    # 1. Fetch KYC profile
    kyc_row = session.exec(select(KycProfile).where(KycProfile.user_id == current_user.id)).first()
    kyc_data = None
    if kyc_row:
        kyc_data = {
            "first_name": kyc_row.first_name,
            "last_name": kyc_row.last_name,
            "dob": kyc_row.dob,
            "gender": kyc_row.gender,
            "document_type": kyc_row.document_type,
            "nin_masked": kyc_row.id_number[:4] + "****" + kyc_row.id_number[-2:] if kyc_row.id_number and len(kyc_row.id_number) >= 6 else None,
            "sim_registered_name": kyc_row.sim_registered_name,
            "sim_carrier": kyc_row.sim_carrier,
            "kyc_status": kyc_row.kyc_status,
            "verified_at": kyc_row.verified_at
        }

    # 2. Fetch security email
    sec_email = session.exec(select(UserSecurityEmail).where(UserSecurityEmail.user_id == current_user.id)).first()

    # 3. Fetch payment methods & payout destinations (sanitized)
    payout_methods = session.exec(select(UserPayoutDestination).where(UserPayoutDestination.user_id == current_user.id)).all()
    payment_methods = session.exec(select(UserPaymentMethod).where(UserPaymentMethod.user_id == current_user.id)).all()

    # 4. Fetch group memberships
    memberships = session.exec(select(GroupMembership).where(GroupMembership.user_id == current_user.id)).all()
    group_ids = [m.group_id for m in memberships]
    groups = session.exec(select(Group).where(Group.group_id.in_(group_ids))).all() if group_ids else []
    group_dict = {g.group_id: g.name for g in groups}

    group_history = [
        {
            "group_id": m.group_id,
            "group_name": group_dict.get(m.group_id, "Unknown"),
            "role": m.role,
            "status": m.status,
            "total_contributed": m.total_contributed,
            "joined_at": m.joined_at,
            "left_at": m.left_at
        }
        for m in memberships
    ]

    return {
        "status": "success",
        "exported_at": int(time.time() * 1000),
        "data": {
            "user_id": str(current_user.id),
            "phone_number": current_user.phone_number,
            "full_name": current_user.full_name,
            "profile_picture_url": current_user.profile_picture_url,
            "avatar_color": current_user.avatar_color,
            "about_status": current_user.about_status,
            "kyc_tier": current_user.kyc_tier,
            "trust_score": current_user.trust_score,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
            "security_email": sec_email.email if (sec_email and sec_email.is_verified) else None,
            "identity_verification": kyc_data,
            "registered_payout_destinations": [
                {
                    "network": p.network,
                    "phone_number": p.phone_number[:6] + "****" + p.phone_number[-2:] if len(p.phone_number) >= 8 else p.phone_number,
                    "account_holder_name": p.account_holder_name,
                    "is_verified": p.is_verified
                }
                for p in payout_methods
            ],
            "registered_payment_methods": [
                {
                    "network": m.network,
                    "phone_number": m.phone_number[:6] + "****" + m.phone_number[-2:] if len(m.phone_number) >= 8 else m.phone_number,
                    "is_auto_pay_enabled": m.is_auto_pay_enabled
                }
                for m in payment_methods
            ],
            "group_participations": group_history
        }
    }


# ---------------------------------------------------------------------------
# GDPR: Delete Account
# ---------------------------------------------------------------------------

@router.delete("/me", summary="GDPR: Delete / Anonymize User Account")
async def delete_user_account(
    payload: DeleteAccountRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    GDPR Article 17: Right to Erasure ('Right to be Forgotten').

    Enforces a comprehensive set of financial pre-checks before allowing account deletion.
    The user must resolve ALL financial entanglements first:

    Pre-checks (in order):
      1.  Confirmation phrase  → Must type 'DELETE MY ACCOUNT'
      2.  App PIN              → bcrypt verified if PIN is set
      3.  Unpaid obligations   → No PENDING or LATE contributions in any group
      4.  Running group owner   → Cannot own any ACTIVE group with live funds or co-members
      5.  Active member of running group → Cannot be in any group that has a balance/live cycle
      6.  Pending payout       → Cannot delete while owed a payout (PENDING/PROCESSING)
      7.  Active guarantor     → Cannot exit while guaranteeing another member's loan
      8.  Active loan          → Cannot delete while holding an unpaid club loan
      9.  Unpaid penalties     → All late fees must be cleared first
      10. Association arrears  → No outstanding dues balance in any association group
      11. Pending turn swaps   → No open swap requests that others are waiting on
    """

    # ── STEP 1: Confirmation Phrase ─────────────────────────────────────────
    if payload.confirmation.strip().upper() != "DELETE MY ACCOUNT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="To confirm deletion, you must type 'DELETE MY ACCOUNT'."
        )

    # ── STEP 2: App PIN Verification ────────────────────────────────────────
    if current_user.hashed_pin:
        if not payload.app_pin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="App PIN is required to authorize account deletion."
            )
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        if not pwd_context.verify(payload.app_pin.strip(), current_user.hashed_pin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid App PIN."
            )

    # ── STEP 3: Unpaid Group Obligations ────────────────────────────────────
    unpaid_obligations = session.exec(
        select(MemberObligation).where(
            MemberObligation.user_id == current_user.id,
            MemberObligation.status.in_(["PENDING", "LATE"])
        )
    ).first()

    if unpaid_obligations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Account cannot be deleted: you have outstanding contribution obligations "
                "(PENDING or LATE) in one or more groups. Please settle all dues first."
            )
        )

    # ── STEP 4: Active Group Ownership / Running Group Guard ────────────────
    # Block deletion if the user owns ANY active group that is currently "running":
    # i.e. it has live pooled funds (total_balance > 0) OR has other active members.
    # This is a hard block — there is no auto-close shortcut because deleting an
    # account while a group is live risks losing other people's money.
    owned_running_groups = session.exec(
        select(Group).where(
            Group.created_by_user_id == current_user.id,
            Group.status == "ACTIVE",
            (Group.total_balance > 0) | (Group.member_count > 1)
        )
    ).all()

    if owned_running_groups:
        names = ", ".join(f"'{g.name}'" for g in owned_running_groups)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Account cannot be deleted: you are the owner of {len(owned_running_groups)} running group(s): {names}. "
                "These groups currently hold live funds or have active co-members whose money could be at risk. "
                "Please transfer ownership or fully dissolve each group (withdraw all balances and remove all members) before deleting your account."
            )
        )

    # ── STEP 5: Active Member of a Running Group with a Balance ─────────────
    # Block if user is a member of any ACTIVE group that still has a live balance
    # (total_balance > 0). This protects other members' pooled money.
    active_memberships = session.exec(
        select(GroupMembership).where(
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).all()

    active_member_group_ids = [m.group_id for m in active_memberships]

    if active_member_group_ids:
        funded_groups = session.exec(
            select(Group).where(
                Group.group_id.in_(active_member_group_ids),
                Group.status == "ACTIVE",
                Group.total_balance > 0
            )
        ).all()

        if funded_groups:
            names = ", ".join(f"'{g.name}'" for g in funded_groups)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Account cannot be deleted: you are an active member of {len(funded_groups)} "
                    f"group(s) that currently hold pooled funds: {names}. "
                    "Leaving would risk other members' money. Please wait for the cycle to complete, "
                    "withdraw your contribution, or ask the group admin to release your share first."
                )
            )

    # ── STEP 6: Pending Payout Owed to User ─────────────────────────────────
    pending_payout = session.exec(
        select(GroupPayout).where(
            GroupPayout.user_id == current_user.id,
            GroupPayout.status.in_(["PENDING", "PROCESSING"])
        )
    ).first()

    if pending_payout:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Account cannot be deleted: you have a pending payout that has not yet been "
                "disbursed to your account. Please wait for the payout to complete first."
            )
        )

    # ── STEP 7: Active Guarantor Pledge ─────────────────────────────────────
    # Cannot leave while legally backing someone else's loan (or while someone backs yours)
    active_guarantee_given = session.exec(
        select(GuarantorPledge).where(
            GuarantorPledge.guarantor_user_id == current_user.id,
            GuarantorPledge.status == "ACTIVE"
        )
    ).first()

    if active_guarantee_given:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Account cannot be deleted: you are actively guaranteeing another member's loan. "
                "You cannot exit until the loan is fully repaid or the guarantee is released."
            )
        )

    active_guarantee_received = session.exec(
        select(GuarantorPledge).where(
            GuarantorPledge.borrower_user_id == current_user.id,
            GuarantorPledge.status == "ACTIVE"
        )
    ).first()

    if active_guarantee_received:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Account cannot be deleted: you have an active loan that is being guaranteed by "
                "other members. Please repay your loan in full before deleting your account."
            )
        )

    # ── STEP 8: Active Investment Club Loan ─────────────────────────────────
    active_loan = session.exec(
        select(InvestmentClubLoan).where(
            InvestmentClubLoan.user_id == current_user.id,
            InvestmentClubLoan.status.in_(["APPROVED", "DISBURSED"])
        )
    ).first()

    if active_loan:
        remaining = active_loan.total_due_amount - active_loan.amount_repaid
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Account cannot be deleted: you have an outstanding investment club loan "
                f"with UGX {remaining:,} still unpaid. Please repay the loan in full first."
            )
        )

    # ── STEP 9: Unpaid Penalties / Late Fees ────────────────────────────────
    unpaid_penalty = session.exec(
        select(GroupPenalty).where(
            GroupPenalty.user_id == current_user.id,
            GroupPenalty.is_paid == False
        )
    ).first()

    if unpaid_penalty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Account cannot be deleted: you have unpaid late fee penalties in one or more groups. "
                "Please clear all outstanding penalties first."
            )
        )

    # ── STEP 10: Association Dues Arrears ───────────────────────────────────
    dues_in_arrears = session.exec(
        select(AssociationMemberDuesStanding).where(
            AssociationMemberDuesStanding.user_id == current_user.id,
            AssociationMemberDuesStanding.outstanding_arrears_balance > 0
        )
    ).first()

    if dues_in_arrears:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Account cannot be deleted: you have outstanding association dues arrears of "
                f"UGX {dues_in_arrears.outstanding_arrears_balance:,}. "
                "Please settle your dues balance first."
            )
        )

    # ── STEP 11: Pending Turn Swap Requests ─────────────────────────────────
    pending_swap = session.exec(
        select(TurnSwapRequest).where(
            TurnSwapRequest.requester_user_id == current_user.id,
            TurnSwapRequest.status == "PENDING"
        )
    ).first()

    if pending_swap:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Account cannot be deleted: you have a pending turn-swap request awaiting "
                "a response. Please cancel it before deleting your account."
            )
        )

    # ════════════════════════════════════════════════════════════════════════
    # ALL CHECKS PASSED — Begin Safe Anonymization
    # ════════════════════════════════════════════════════════════════════════

    # Soft-leave / mark inactive in all active memberships
    now_ms = int(time.time() * 1000)
    for m in active_memberships:
        m.status = "DELETED"
        m.left_at = now_ms
        session.add(m)

    # Wipe Secondary / Backup Email
    sec_email = session.exec(select(UserSecurityEmail).where(UserSecurityEmail.user_id == current_user.id)).first()
    if sec_email:
        session.delete(sec_email)

    # Wipe Payment Methods & Payout Destinations
    payout_accounts = session.exec(select(UserPayoutDestination).where(UserPayoutDestination.user_id == current_user.id)).all()
    for pa in payout_accounts:
        session.delete(pa)

    payment_methods = session.exec(select(UserPaymentMethod).where(UserPaymentMethod.user_id == current_user.id)).all()
    for pm in payment_methods:
        session.delete(pm)

    # Anonymize KYC Profile (Erasing PII while retaining audit integrity)
    kyc_row = session.exec(select(KycProfile).where(KycProfile.user_id == current_user.id)).first()
    if kyc_row:
        kyc_row.first_name = "DELETED"
        kyc_row.last_name = "USER"
        kyc_row.id_number = f"ANON_{uuid.uuid4().hex[:8]}"
        kyc_row.photo_base64 = None
        kyc_row.sim_registered_name = None
        session.add(kyc_row)

    # Anonymize core User record (Right to be Forgotten)
    anonymized_id = uuid.uuid4().hex[:8]
    current_user.full_name = f"Deleted User {anonymized_id}"
    current_user.phone_number = f"+25600000{anonymized_id}"
    current_user.profile_picture_url = None
    current_user.about_status = "Account closed"
    current_user.fcm_token = None
    current_user.primary_device_id = None
    current_user.hashed_pin = None
    current_user.is_online = False
    current_user.kyc_status = "DEACTIVATED"

    session.add(current_user)
    session.commit()

    # Real-Time Kick & Force Disconnect
    await ws_manager.force_disconnect_user(str(current_user.id), reason="Account deleted by user request")

    return {
        "status": "success",
        "message": "Your Microbond account and personal data have been deleted and anonymized in accordance with GDPR principles."
    }
