import uuid
from sqlmodel import Session
from app.models.group.chat import GroupChatMessage
from app.services.websocket_manager import ws_manager
from fastapi import BackgroundTasks
from app.services.push_notifications import notify_all_group_members

def broadcast_system_message_sync(
    group_id: str,
    message_text: str,
    message_type: str,
    sender_id: str,
    session: Session,
    background_tasks: BackgroundTasks
):
    """
    Utility function to save a system message to the DB and broadcast it via WebSockets in the background.
    """
    system_message = GroupChatMessage(
        client_message_id=str(uuid.uuid4()),
        group_id=group_id,
        sender_id=sender_id,
        message_type=message_type,
        message_text=message_text,
        status="SENT"
    )
    session.add(system_message)
    try:
        session.commit()
        session.refresh(system_message)
    except Exception:
        session.rollback()
        return None
        
    background_tasks.add_task(
        ws_manager.broadcast_to_group,
        group_id,
        {
            "event_type": "NEW_MESSAGE",
            "message": system_message.model_dump(mode="json")
        }
    )
    
    # Trigger offline push notifications
    title = f"System Update"
    body = message_text
    background_tasks.add_task(
        notify_all_group_members,
        group_id=group_id,
        sender_id=sender_id,
        title=title,
        body=body,
        data={"type": "chat_message", "group_id": group_id, "message_id": str(system_message.id)}
    )
    
    return system_message
