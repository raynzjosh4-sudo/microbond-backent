from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import Optional, List, Union
from pydantic import BaseModel

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.chat import GroupChatMessage
from app.models.group.settings import GroupGovernanceSettings
from app.services.websocket_manager import ws_manager

from fastapi import BackgroundTasks
import uuid
import asyncio
import logging

logger = logging.getLogger(__name__)

from app.services.push_notifications import notify_all_group_members

router = APIRouter(prefix="/api/v1/groups", tags=["Group Chat"])

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
class SendMessageRequest(BaseModel):
    client_message_id: str
    message_type: str = "TEXT" # TEXT, SYSTEM_EVENT, VOTE, MEDIA
    message_text: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None
    media_mime_type: Optional[str] = None
    media_size_bytes: Optional[int] = None
    media_duration_seconds: Optional[int] = None
    reply_to_message_id: Optional[Union[str, int]] = None

@router.post("/{group_id}/chat/messages", summary="Send a chat message to the group")
async def send_chat_message(
    group_id: str,
    request: SendMessageRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Unified endpoint to save ANY type of chat message (text, vote, system event, or pre-uploaded media URL).
    """
    # 1. Verify User is a member
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    
    if not membership:
        raise HTTPException(status_code=403, detail="You must be an active member to send messages to this group.")

    # 2. Check Governance Permissions: Only admins can send messages if members_can_send_messages is false
    if membership.role != "ADMIN":
        gov_settings = session.exec(
            select(GroupGovernanceSettings).where(GroupGovernanceSettings.group_id == group_id)
        ).first()
        if gov_settings and not gov_settings.members_can_send_messages:
            raise HTTPException(
                status_code=403,
                detail="Only group admins can send messages in this group."
            )

    # 3. Idempotency check (prevent duplicate messages on bad network)
    existing_msg = session.exec(
        select(GroupChatMessage).where(GroupChatMessage.client_message_id == request.client_message_id)
    ).first()
    if existing_msg:
        return {"message": "Message already sent", "data": existing_msg}

    # 3. Sanitize and resolve reply_to_message_id (accepts message UUID id or client_message_id)
    reply_id: Optional[uuid.UUID] = None
    if request.reply_to_message_id is not None:
        raw_val = str(request.reply_to_message_id).strip()
        if raw_val and raw_val != "0" and raw_val.lower() != "string" and raw_val.lower() != "null":
            # 1. Try finding message directly by primary key UUID
            try:
                candidate_uuid = uuid.UUID(raw_val)
                ref_msg = session.exec(
                    select(GroupChatMessage).where(GroupChatMessage.id == candidate_uuid)
                ).first()
                if ref_msg:
                    reply_id = ref_msg.id
            except ValueError:
                candidate_uuid = None

            # 2. If not found by primary key, try looking up by client_message_id
            if reply_id is None:
                ref_msg = session.exec(
                    select(GroupChatMessage).where(GroupChatMessage.client_message_id == raw_val)
                ).first()
                if ref_msg:
                    reply_id = ref_msg.id

    # 4. Save to database
    new_message = GroupChatMessage(
        client_message_id=request.client_message_id,
        group_id=group_id,
        sender_id=str(current_user.id),
        message_type=request.message_type,
        message_text=request.message_text,
        media_url=request.media_url,
        media_type=request.media_type,
        media_mime_type=request.media_mime_type,
        media_size_bytes=request.media_size_bytes,
        media_duration_seconds=request.media_duration_seconds,
        reply_to_message_id=reply_id,
        status="SENT"
    )

    session.add(new_message)
    try:
        session.commit()
        session.refresh(new_message)
    except Exception as e:
        session.rollback()
        logger.exception(f"Failed to save message in group {group_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save message: {str(e)}")

    # 4. Trigger WebSockets to broadcast this to active clients instantly
    await ws_manager.broadcast_to_group(
        group_id,
        {
            "event_type": "NEW_MESSAGE",
            "message": new_message.model_dump(mode="json")
        },
        exclude_user_id=str(current_user.id) # The sender already has the message locally
    )

    # 5. Trigger offline push notifications for the rest of the group
    title = f"New message from {current_user.full_name}"
    body = request.message_text or "Sent an attachment"
    if request.message_type != "TEXT":
        body = f"Sent a {request.message_type.lower()}"
        
    background_tasks.add_task(
        notify_all_group_members,
        group_id=group_id,
        sender_id=str(current_user.id),
        title=title,
        body=body,
        data={"type": "chat_message", "group_id": group_id, "message_id": str(new_message.id)}
    )

    return {"message": "Message sent successfully", "data": new_message}

@router.get("/{group_id}/chat/messages", summary="Get chat messages for a group")
async def get_chat_messages(
    group_id: str,
    limit: int = Query(50, le=100),
    before_created_at: Optional[int] = Query(None, description="Timestamp for pagination (scrolling up)"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves the chat history for a group, supporting extremely fast pagination.
    """
    # Verify User is a member
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    
    if not membership:
        raise HTTPException(status_code=403, detail="You must be a member to view messages.")

    stmt = select(GroupChatMessage).where(
        GroupChatMessage.group_id == group_id,
        GroupChatMessage.is_deleted == False
    )
    
    # Pagination cursor (used for scrolling up into history)
    if before_created_at:
        stmt = stmt.where(GroupChatMessage.created_at < before_created_at)
        
    # Order by newest first, limited batch
    stmt = stmt.order_by(GroupChatMessage.created_at.desc()).limit(limit)
    
    messages = session.exec(stmt).all()
    
    return {"data": messages}
