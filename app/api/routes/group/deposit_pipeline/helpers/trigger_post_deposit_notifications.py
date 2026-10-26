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
    session: Session,
    cycle_deposit: int = None,
    surplus: int = 0,
    obligation_status: str = "PAID",
    remaining_due: int = 0,
    cycle_number: int = 1,
    ref_id: str = None
):
    """
    Called by the payment webhook/confirmation handler after a successful deposit.
    - Sends SMS receipt if member is opted in.
    - Sends email receipt if member has a verified security email.
    - Sends targeted push notifications (Regular, Advance 4x, or Partial).
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
            from app.services.communication.sms.helpers.send_sms import send_sms
            sms_text = f"Microbond: {amount_deposited:,} {currency} received for {group_name} Cycle {cycle_number}."
            if ref_id:
                sms_text += f" Ref: {ref_id}."
            sms_text += " Thank you!"
            try:
                send_sms(user.phone_number, sms_text)
                membership.pending_sms_fee_ugx = 0
                session.add(membership)
                session.commit()
            except Exception as sms_err:
                logger.warning(f"[DEPOSIT SMS] Failed: {sms_err}")

        # 2. Push: personal deposit receipt to the depositor (Events 9, 10, 11)
        if surplus > 0:
            push_title = "🌟 Advance Deposit Settled"
            push_body = (
                f"{(cycle_deposit or amount_deposited):,} {currency} applied to Cycle {cycle_number}. "
                f"{surplus:,} {currency} stored in your prepaid balance covering future cycles."
            )
        elif obligation_status == "PARTIAL":
            push_title = "⚠️ Partial Deposit Recorded"
            push_body = (
                f"Received {amount_deposited:,} {currency}. "
                f"You still owe {remaining_due:,} {currency} to complete your Cycle {cycle_number} contribution."
            )
        else:
            push_title = "✅ Deposit Confirmed"
            push_body = f"Your {amount_deposited:,} {currency} contribution for Cycle {cycle_number} has been settled in {group_name}."

        if user.fcm_token:
            send_push_notification(
                token=user.fcm_token,
                title=push_title,
                body=push_body,
                data={
                    "type": "DEPOSIT_RECEIPT",
                    "group_id": group_id,
                    "cycle_number": str(cycle_number)
                }
            )

        # 3. Push: broadcast to all other group members (social accountability nudge)
        broadcast_title = f"💰 {member_name} just deposited"
        if surplus > 0:
            broadcast_body = f"{member_name} deposited {amount_deposited:,} {currency} ({(cycle_deposit or amount_deposited):,} for Cycle {cycle_number} + {surplus:,} advance) in '{group_name}'."
        elif obligation_status == "PARTIAL":
            broadcast_body = f"{member_name} made a partial deposit of {amount_deposited:,} {currency} in '{group_name}'."
        else:
            broadcast_body = f"{member_name} deposited {currency} {amount_deposited:,} in '{group_name}'."

        try:
            from app.services.push_notifications import notify_all_group_members_sync
            notify_all_group_members_sync(
                group_id=group_id,
                sender_id=str(user_id),
                title=broadcast_title,
                body=broadcast_body,
                data={"type": "DEPOSIT_BROADCAST", "group_id": group_id}
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
