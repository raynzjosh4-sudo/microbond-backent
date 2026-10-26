import uuid
import logging
from typing import Optional, List
from sqlmodel import Session
from app.models.group.chat import GroupChatMessage
from app.services.websocket_manager import ws_manager
from fastapi import BackgroundTasks
from app.services.push_notifications import notify_all_group_members, notify_all_group_members_sync
from app.core.database import engine

logger = logging.getLogger(__name__)


def broadcast_system_message_sync(
    group_id: str,
    message_text: str,
    message_type: str = "SYSTEM_EVENT",
    sender_id: str = "SYSTEM",
    session: Optional[Session] = None,
    background_tasks: Optional[BackgroundTasks] = None,
    attachments: Optional[list] = None
):
    """
    Utility function to save a system message to the DB and broadcast it via WebSockets & Push in the background.
    Works safely both inside FastAPI request context and in background worker threads.
    """
    system_message = GroupChatMessage(
        client_message_id=str(uuid.uuid4()),
        group_id=group_id,
        sender_id=sender_id,
        message_type=message_type,
        message_text=message_text,
        attachments=attachments,
        status="SENT"
    )

    should_close = False
    active_session = session
    if active_session is None:
        active_session = Session(engine)
        should_close = True

    try:
        active_session.add(system_message)
        active_session.commit()
        active_session.refresh(system_message)
    except Exception as e:
        active_session.rollback()
        logger.warning(f"Failed saving system message: {e}")
        if should_close:
            active_session.close()
        return None

    if should_close:
        active_session.close()

    # WebSocket Broadcast
    if background_tasks is not None:
        background_tasks.add_task(
            ws_manager.broadcast_to_group,
            group_id,
            {
                "event_type": "NEW_MESSAGE",
                "message": system_message.model_dump(mode="json")
            }
        )
    else:
        try:
            ws_manager.broadcast_to_group_sync(
                group_id,
                {
                    "event_type": "NEW_MESSAGE",
                    "message": system_message.model_dump(mode="json")
                }
            )
        except Exception:
            pass

    # Push Notification Broadcast
    title = "System Update"
    body = message_text
    data = {"type": "chat_message", "group_id": group_id, "message_id": str(system_message.id)}

    if background_tasks is not None:
        background_tasks.add_task(
            notify_all_group_members,
            group_id=group_id,
            sender_id=sender_id,
            title=title,
            body=body,
            data=data
        )
    else:
        notify_all_group_members_sync(
            group_id=group_id,
            sender_id=sender_id,
            title=title,
            body=body,
            data=data
        )

    return system_message
