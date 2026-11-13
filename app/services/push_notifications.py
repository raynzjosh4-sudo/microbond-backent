import logging
from typing import List, Optional
from sqlmodel import Session, select
import asyncio

from app.core.database import engine
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.core.firebase_config import send_push_notification

logger = logging.getLogger(__name__)

async def notify_all_group_members(
    group_id: str, 
    sender_id: str, 
    title: str, 
    body: str, 
    data: dict,
    include_sender_in_inbox: bool = False,
):
    """
    Sends an FCM push notification to all active members of the group except the sender.
    (Note: iOS/Android natively suppresses the UI banner if the app is already open in the foreground).
    """
    def _fetch_tokens():
        # Connect to DB synchronously inside threadpool
        with Session(engine) as session:
            # Keep the sender in the recipient set for inbox delivery, but
            # suppress their push notification below.
            member_query = select(GroupMembership).where(
                GroupMembership.group_id == group_id,
                GroupMembership.status == "ACTIVE",
            )
            members = session.exec(member_query).all()
            
            user_ids = [m.user_id for m in members]
            if not user_ids:
                return []
                
            # 2. Get FCM tokens for those users
            users = session.exec(
                select(User).where(User.id.in_(user_ids))
            ).all()
            
            return [
                (u.id, u.fcm_token, sender_id == "SYSTEM" or str(u.id) != sender_id)
                for u in users
            ]

    # Run DB query in a thread to avoid blocking event loop
    loop = asyncio.get_running_loop()
    recipients = await loop.run_in_executor(None, _fetch_tokens)

    from app.services.notification_delivery import create_notifications_for_users

    inbox_recipients = [
        user_id
        for user_id, _, is_not_sender in recipients
        if include_sender_in_inbox or is_not_sender
    ]
    await loop.run_in_executor(
        None,
        create_notifications_for_users,
        inbox_recipients,
        title,
        body,
        data,
    )
    
    # Send FCM notifications concurrently using gather
    tasks = [
        loop.run_in_executor(None, send_push_notification, token, title, body, data) 
        for _, token, is_not_sender in recipients
        if token and is_not_sender
    ]
    tokens = [
        token
        for _, token, is_not_sender in recipients
        if token and is_not_sender
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    sent_count = 0
    for idx, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Failed to send push notification to token {tokens[idx]}: {result}")
        elif result:
            sent_count += 1
            
    if sent_count > 0:
        logger.info(f"Sent {sent_count} push notifications for group {group_id} concurrently")


def notify_all_group_members_sync(
    group_id: str, 
    sender_id: str, 
    title: str, 
    body: str, 
    data: dict,
    include_sender_in_inbox: bool = False,
):
    """
    Synchronous wrapper to broadcast push notifications to all group members.
    Works safely inside or outside an active asyncio event loop.
    """
    try:
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
        if loop and loop.is_running():
            asyncio.create_task(
                notify_all_group_members(
                    group_id,
                    sender_id,
                    title,
                    body,
                    data,
                    include_sender_in_inbox,
                )
            )
        else:
            asyncio.run(
                notify_all_group_members(
                    group_id,
                    sender_id,
                    title,
                    body,
                    data,
                    include_sender_in_inbox,
                )
            )
    except Exception as e:
        logger.warning(f"notify_all_group_members_sync error: {e}")


def send_push_to_user(user_id, title: str, body: str, data: dict = None):
    """
    Helper to look up user's FCM token and dispatch push notification.
    """
    import uuid
    try:
        uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
        with Session(engine) as session:
            user = session.get(User, uid)
            if user and user.fcm_token:
                return send_push_notification(user.fcm_token, title, body, data or {})
    except Exception as e:
        logger.warning(f"send_push_to_user error for {user_id}: {e}")
    return None
