import asyncio
import logging
from sqlmodel import Session, select

from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.user.security_email import UserSecurityEmail
from app.communications.sms_service import SMS_FEE_UGX, send_deposit_receipt_sms
from app.core.firebase_config import send_push_notification
from app.services.push_notifications import notify_all_group_members

logger = logging.getLogger(__name__)

def trigger_post_deposit_notifications(
    group_id: str,
    user_id,
    amount_deposited: int,
    session: Session
):
    """
    Called by the payment webhook/confirmation handler after a successful deposit.
    - Sends SMS receipt if member is opted in.
    - Sends email receipt if member has a verified security email.
    - Resets pending_sms_fee_ugx to 0 (it was already billed into the quote).
    """
    try:
        user = session.exec(select(User).where(User.id == user_id)).first()
        group = session.exec(select(Group).where(Group.group_id == group_id)).first()
        membership = session.exec(
            select(GroupMembership).where(
                GroupMembership.group_id == group_id,
                GroupMembership.user_id == user_id
            )
        ).first()

        if not user or not group or not membership:
            return

        member_name = user.full_name or "Member"
        group_name = group.name
        currency = group.currency or "UGX"

        # 1. SMS receipt (if opted in)
        if membership.sms_reminders_opted_in and user.phone_number:
            send_deposit_receipt_sms(
                phone_number=user.phone_number,
                member_name=member_name,
                group_name=group_name,
                amount_deposited=amount_deposited,
                sms_fee=SMS_FEE_UGX,
                currency=currency
            )
            # Reset pending fee counter
            membership.pending_sms_fee_ugx = 0
            session.add(membership)
            session.commit()

        # 3. Push: personal deposit receipt to the depositor
        if user.fcm_token:
            send_push_notification(
                token=user.fcm_token,
                title="Deposit Received ✅",
                body=f"Your {currency} {amount_deposited:,} deposit to '{group_name}' was recorded successfully.",
                data={"type": "DEPOSIT_RECEIPT", "group_id": group_id}
            )

        # 4. Push: broadcast to all other group members (social accountability nudge)
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(
                    notify_all_group_members(
                        group_id=group_id,
                        sender_id=str(user_id),
                        title=f"💰 {member_name} just deposited",
                        body=f"{member_name} deposited {currency} {amount_deposited:,} in '{group_name}'.",
                        data={"type": "DEPOSIT_BROADCAST", "group_id": group_id}
                    )
                )
            else:
                loop.run_until_complete(
                    notify_all_group_members(
                        group_id=group_id,
                        sender_id=str(user_id),
                        title=f"💰 {member_name} just deposited",
                        body=f"{member_name} deposited {currency} {amount_deposited:,} in '{group_name}'.",
                        data={"type": "DEPOSIT_BROADCAST", "group_id": group_id}
                    )
                )
        except Exception as push_err:
            logger.warning(f"[DEPOSIT_BROADCAST_PUSH] Failed: {push_err}")

        # 2. Email receipt (if verified security email exists)
        security_email_row = session.exec(
            select(UserSecurityEmail).where(
                UserSecurityEmail.user_id == user_id,
                UserSecurityEmail.is_verified == True
            )
        ).first()

        if security_email_row and membership.sms_reminders_opted_in:
            try:
                from app.services.communication.email_service import EmailNotificationService
                from app.services.communication.email_templates import build_deposit_receipt_email

                html_body = build_deposit_receipt_email(
                    member_name=member_name,
                    group_name=group_name,
                    amount_deposited=amount_deposited,
                    sms_fee_ugx=SMS_FEE_UGX,
                    currency=currency
                )
                asyncio.run(EmailNotificationService._dispatch(
                    recipient_email=security_email_row.email,
                    subject=f"Deposit Received — {group_name}",
                    html_body=html_body
                ))
            except Exception as email_err:
                logger.warning(f"[DEPOSIT EMAIL] Failed: {email_err}")

    except Exception as e:
        logger.error(f"[POST_DEPOSIT_NOTIFY] Error: {e}")
