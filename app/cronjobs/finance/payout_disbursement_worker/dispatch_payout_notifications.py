import logging
import asyncio
from sqlmodel import Session, select
from app.models.group.group import Group, GroupMembership
from app.models.group.finance import GroupPayout
from app.models.user.user import User
from app.models.user.security_email import UserSecurityEmail
from app.services.group.payout_destination_resolver import ResolvedPayoutAccount
from app.core.firebase_config import send_push_notification
from app.services.push_notifications import notify_all_group_members
from app.communications.sms_service import send_payout_disbursed_sms
from app.services.communication.email_service import EmailNotificationService
from app.services.communication.email_templates import build_payout_disbursed_email

logger = logging.getLogger(__name__)


def dispatch_payout_notifications(
    session: Session,
    user: User,
    group: Group,
    payout: GroupPayout,
    chosen_account: ResolvedPayoutAccount,
    masked_acc: str
):
    member_name = user.full_name or "Member"
    amount_str = f"{payout.amount_expected:,} UGX"

    # A. Push Notification to Recipient
    if user.fcm_token:
        try:
            send_push_notification(
                token=user.fcm_token,
                title="💰 Payout Received!",
                body=f"Your payout of {amount_str} for {group.name} (Round {payout.cycle_number}) has been sent to {chosen_account.provider_name} ({masked_acc}).",
                data={
                    "type": "PAYOUT_COMPLETED",
                    "group_id": payout.group_id,
                    "payout_id": str(payout.id),
                    "amount": str(payout.amount_expected)
                }
            )
        except Exception as ex:
            logger.warning(f"[PAYOUT_NOTIF] FCM recipient push failed: {ex}")

    # B. Push Notification to Group Members
    try:
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        coro = notify_all_group_members(
            group_id=payout.group_id,
            sender_id=str(user.id),
            title=f"🎉 {group.name} Payout Complete",
            body=f"{member_name} received their Round {payout.cycle_number} payout of {amount_str}!",
            data={
                "type": "GROUP_PAYOUT_EVENT",
                "group_id": payout.group_id,
                "cycle_number": str(payout.cycle_number)
            }
        )

        if loop and loop.is_running():
            asyncio.create_task(coro)
        else:
            asyncio.run(coro)
    except Exception as ex:
        logger.warning(f"[PAYOUT_NOTIF] Group broadcast push failed: {ex}")

    # C. SMS Notification (Africa's Talking)
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == payout.group_id,
            GroupMembership.user_id == user.id
        )
    ).first()

    if membership and membership.sms_reminders_opted_in and user.phone_number:
        try:
            send_payout_disbursed_sms(
                phone_number=user.phone_number,
                member_name=member_name,
                group_name=group.name,
                amount_paid=payout.amount_expected,
                provider_name=chosen_account.provider_name,
                masked_account=masked_acc,
                currency="UGX"
            )
        except Exception as ex:
            logger.warning(f"[PAYOUT_NOTIF] SMS alert failed: {ex}")

    # D. Verified Security Email (Resend)
    security_email = session.exec(
        select(UserSecurityEmail).where(
            UserSecurityEmail.user_id == user.id,
            UserSecurityEmail.is_verified == True
        )
    ).first()

    if security_email and security_email.email:
        try:
            html_body = build_payout_disbursed_email(
                member_name=member_name,
                group_name=group.name,
                amount_paid=payout.amount_expected,
                cycle_number=payout.cycle_number,
                provider_name=chosen_account.provider_name,
                masked_account=masked_acc,
                currency="UGX"
            )
            EmailNotificationService.send_email(
                to_email=security_email.email,
                subject=f"Payout Disbursed ({amount_str}) — {group.name}",
                html_content=html_body
            )
        except Exception as ex:
            logger.warning(f"[PAYOUT_NOTIF] Email alert failed: {ex}")
