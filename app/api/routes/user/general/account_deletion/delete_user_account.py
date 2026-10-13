import time
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.user.kyc import KycProfile
from app.models.user.security_email import UserSecurityEmail
from app.models.user.userpaymentmethod.payment_method import UserPaymentMethod
from app.models.user.userpayoutaccount.payout_destination import (
    UserPayoutDestination,
)
from app.models.group.group import Group, GroupMembership
from app.models.group.finance import (
    MemberObligation,
    GroupPayout,
    GroupPenalty,
    GuarantorPledge,
    TurnSwapRequest,
)
from app.models.group.investment_association import (
    InvestmentClubLoan,
    AssociationMemberDuesStanding,
)
from app.services.websocket_manager import ws_manager
from .schemas import DeleteAccountRequest

router = APIRouter()


@router.delete("/me", summary="GDPR: Delete / Anonymize User Account")
async def delete_user_account(
    payload: DeleteAccountRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # ── STEP 1: Confirmation Phrase ─────────────────────────────────────────
    if payload.confirmation.strip().upper() != "DELETE MY ACCOUNT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="To confirm deletion, you must type 'DELETE MY ACCOUNT'.",
        )

    # ── STEP 2: App PIN Verification ────────────────────────────────────────
    if current_user.hashed_pin:
        if not payload.app_pin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="App PIN is required to authorize account deletion.",
            )
        from passlib.context import CryptContext

        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        if not pwd_context.verify(
            payload.app_pin.strip(), current_user.hashed_pin
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Invalid App PIN."
            )

    # ── STEP 3: Unpaid Group Obligations ────────────────────────────────────
    unpaid_obligations = session.exec(
        select(MemberObligation).where(
            MemberObligation.user_id == current_user.id,
            MemberObligation.status.in_(["PENDING", "LATE"]),
        )
    ).first()

    if unpaid_obligations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Account cannot be deleted: you have outstanding contribution obligations "
                "(PENDING or LATE) in one or more groups. Please settle all dues first."
            ),
        )

    # ── STEP 4: Active Group Ownership / Running Group Guard ────────────────
    owned_running_groups = session.exec(
        select(Group).where(
            Group.created_by_user_id == current_user.id,
            Group.status == "ACTIVE",
            (Group.total_balance > 0) | (Group.member_count > 1),
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
            ),
        )

    # ── STEP 5: Active Member of a Running Group with a Balance ─────────────
    active_memberships = session.exec(
        select(GroupMembership).where(
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE",
        )
    ).all()

    active_member_group_ids = [m.group_id for m in active_memberships]

    if active_member_group_ids:
        funded_groups = session.exec(
            select(Group).where(
                Group.group_id.in_(active_member_group_ids),
                Group.status == "ACTIVE",
                Group.total_balance > 0,
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
                ),
            )

    # ── STEP 6: Pending Payout Owed to User ─────────────────────────────────
    pending_payout = session.exec(
        select(GroupPayout).where(
            GroupPayout.user_id == current_user.id,
            GroupPayout.status.in_(["PENDING", "PROCESSING"]),
        )
    ).first()

    if pending_payout:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Account cannot be deleted: you have a pending payout that has not yet been "
                "disbursed to your account. Please wait for the payout to complete first."
            ),
        )

    # ── STEP 7: Active Guarantor Pledge ─────────────────────────────────────
    active_guarantee_given = session.exec(
        select(GuarantorPledge).where(
            GuarantorPledge.guarantor_user_id == current_user.id,
            GuarantorPledge.status == "ACTIVE",
        )
    ).first()

    if active_guarantee_given:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Account cannot be deleted: you are actively guaranteeing another member's loan. "
                "You cannot exit until the loan is fully repaid or the guarantee is released."
            ),
        )

    active_guarantee_received = session.exec(
        select(GuarantorPledge).where(
            GuarantorPledge.borrower_user_id == current_user.id,
            GuarantorPledge.status == "ACTIVE",
        )
    ).first()

    if active_guarantee_received:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Account cannot be deleted: you have an active loan that is being guaranteed by "
                "other members. Please repay your loan in full before deleting your account."
            ),
        )

    # ── STEP 8: Active Investment Club Loan ─────────────────────────────────
    active_loan = session.exec(
        select(InvestmentClubLoan).where(
            InvestmentClubLoan.user_id == current_user.id,
            InvestmentClubLoan.status.in_(["APPROVED", "DISBURSED"]),
        )
    ).first()

    if active_loan:
        remaining = active_loan.total_due_amount - active_loan.amount_repaid
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Account cannot be deleted: you have an outstanding investment club loan "
                f"with UGX {remaining:,} still unpaid. Please repay the loan in full first."
            ),
        )

    # ── STEP 9: Unpaid Penalties / Late Fees ────────────────────────────────
    unpaid_penalty = session.exec(
        select(GroupPenalty).where(
            GroupPenalty.user_id == current_user.id,
            GroupPenalty.is_paid == False,
        )
    ).first()

    if unpaid_penalty:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Account cannot be deleted: you have unpaid late fee penalties in one or more groups. "
                "Please clear all outstanding penalties first."
            ),
        )

    # ── STEP 10: Association Dues Arrears ───────────────────────────────────
    dues_in_arrears = session.exec(
        select(AssociationMemberDuesStanding).where(
            AssociationMemberDuesStanding.user_id == current_user.id,
            AssociationMemberDuesStanding.outstanding_arrears_balance > 0,
        )
    ).first()

    if dues_in_arrears:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Account cannot be deleted: you have outstanding association dues arrears of "
                f"UGX {dues_in_arrears.outstanding_arrears_balance:,}. "
                "Please settle your dues balance first."
            ),
        )

    # ── STEP 11: Pending Turn Swap Requests ─────────────────────────────────
    pending_swap = session.exec(
        select(TurnSwapRequest).where(
            TurnSwapRequest.requester_user_id == current_user.id,
            TurnSwapRequest.status == "PENDING",
        )
    ).first()

    if pending_swap:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Account cannot be deleted: you have a pending turn-swap request awaiting "
                "a response. Please cancel it before deleting your account."
            ),
        )

    # ════════════════════════════════════════════════════════════════════════
    # ALL CHECKS PASSED — Begin Safe Anonymization
    # ════════════════════════════════════════════════════════════════════════
    now_ms = int(time.time() * 1000)
    for m in active_memberships:
        m.status = "DELETED"
        m.left_at = now_ms
        session.add(m)

    sec_email = session.exec(
        select(UserSecurityEmail).where(
            UserSecurityEmail.user_id == current_user.id
        )
    ).first()
    if sec_email:
        session.delete(sec_email)

    payout_accounts = session.exec(
        select(UserPayoutDestination).where(
            UserPayoutDestination.user_id == current_user.id
        )
    ).all()
    for pa in payout_accounts:
        session.delete(pa)

    payment_methods = session.exec(
        select(UserPaymentMethod).where(
            UserPaymentMethod.user_id == current_user.id
        )
    ).all()
    for pm in payment_methods:
        session.delete(pm)

    kyc_row = session.exec(
        select(KycProfile).where(KycProfile.user_id == current_user.id)
    ).first()
    if kyc_row:
        kyc_row.first_name = "DELETED"
        kyc_row.last_name = "USER"
        kyc_row.id_number = f"ANON_{uuid.uuid4().hex[:8]}"
        kyc_row.photo_base64 = None
        kyc_row.sim_registered_name = None
        session.add(kyc_row)

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

    await ws_manager.force_disconnect_user(
        str(current_user.id), reason="Account deleted by user request"
    )

    return {
        "status": "success",
        "message": "Your Microbond account and personal data have been deleted and anonymized in accordance with GDPR principles.",
    }
