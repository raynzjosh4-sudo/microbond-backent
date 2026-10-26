import logging
import asyncio
from sqlmodel import Session, select
from app.models.group.group import Group, GroupMembership
from app.models.group.finance import GroupPayout
from app.models.user.user import User
from app.models.user.security_email import UserSecurityEmail
from app.services.group.payout_destination_resolver import ResolvedPayoutAccount
from app.core.firebase_config import send_push_notification
from app.services.push_notifications import notify_all_group_members, notify_all_group_members_sync
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
    masked_acc: str,
    hold_amount: int = 0,
    disburse_amount: int = None
):
    member_name = user.full_name or "Member"
    curr = group.currency or "UGX"
    if disburse_amount is None:
        disburse_amount = payout.amount_received or payout.amount_expected
    disbursed_str = f"{disburse_amount:,} {curr}"
    hold_str = f" {hold_amount:,} {curr} in security escrow." if hold_amount > 0 else ""

    # A. Push Notification to Recipient (Event 15)
    if user.fcm_token:
        try:
            send_push_notification(
                token=user.fcm_token,
                title="💰 Payout Received!",
                body=f"{disbursed_str} disbursed to your {chosen_account.provider_name} for Cycle {payout.cycle_number}.{hold_str}",
                data={
                    "type": "PAYOUT_COMPLETED",
                    "group_id": payout.group_id,
                    "payout_id": str(payout.id),
                    "amount": str(disburse_amount),
                    "hold_amount": str(hold_amount)
                }
            )
        except Exception as ex:
            logger.warning(f"[PAYOUT_NOTIF] FCM recipient push failed: {ex}")

    # B. Push Notification to Group Members (Event 15)
    try:
        notify_all_group_members_sync(
            group_id=payout.group_id,
            sender_id=str(user.id),
            title=f"🎉 Cycle {payout.cycle_number} Payout Complete",
            body=f"{member_name} received their Round {payout.cycle_number} payout of {disbursed_str}!",
            data={
                "type": "GROUP_PAYOUT_EVENT",
                "group_id": payout.group_id,
                "cycle_number": str(payout.cycle_number)
            }
        )
    except Exception as ex:
        logger.warning(f"[PAYOUT_NOTIF] Group broadcast push failed: {ex}")

    # C. SMS Notification (Opted-in only) (Event 15)
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == payout.group_id,
            GroupMembership.user_id == user.id
        )
    ).first()

    if membership and getattr(membership, "sms_reminders_opted_in", False) and user.phone_number:
        try:
            from app.services.communication.sms.helpers.send_sms import send_sms
            sms_body = f"Microbond: {disbursed_str} disbursed for Cycle {payout.cycle_number} Payout."
            if hold_amount > 0:
                sms_body += f" {hold_amount:,} {curr} held in security escrow until final round."
            send_sms(user.phone_number, sms_body)
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
