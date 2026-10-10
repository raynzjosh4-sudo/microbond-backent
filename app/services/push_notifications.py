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
    data: dict
):
    """
    Sends an FCM push notification to all active members of the group except the sender.
    (Note: iOS/Android natively suppresses the UI banner if the app is already open in the foreground).
    """
    def _fetch_tokens():
        # Connect to DB synchronously inside threadpool
        with Session(engine) as session:
            # 1. Get all active members except sender
            members = session.exec(
                select(GroupMembership).where(
                    GroupMembership.group_id == group_id,
                    GroupMembership.status == "ACTIVE",
                    GroupMembership.user_id != sender_id
                )
            ).all()
            
            user_ids = [m.user_id for m in members]
            if not user_ids:
                return []
                
            # 2. Get FCM tokens for those users
            users = session.exec(
                select(User).where(User.id.in_(user_ids))
            ).all()
            
            return [u.fcm_token for u in users if u.fcm_token]

    # Run DB query in a thread to avoid blocking event loop
    loop = asyncio.get_running_loop()
    tokens = await loop.run_in_executor(None, _fetch_tokens)
    
    # Send FCM notifications concurrently using gather
    tasks = [
        loop.run_in_executor(None, send_push_notification, token, title, body, data) 
        for token in tokens
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
