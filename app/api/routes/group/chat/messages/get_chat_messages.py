import uuid
from collections import defaultdict
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.chat import GroupChatMessage, GroupChatReadReceipt
from app.utils.avatar_colors import resolve_vibrant_avatar_color
from .schemas import ChatMessageItem, ReplyToSummary, ChatMessagesListResponse

router = APIRouter()

@router.get(
    "/{group_id}/chat/messages",
    response_model=ChatMessagesListResponse,
    summary="Get chat messages for a group",
    description="Retrieves the chat history with full sender profiles, quoted reply previews, and read receipt tick statuses."
)
async def get_chat_messages(
    group_id: str,
    limit: int = Query(50, le=100),
    before_created_at: Optional[int] = Query(None, description="Timestamp for pagination (scrolling up)"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves the chat history for a group, supporting fast pagination,
    rich sender profile cards, quoted reply previews, and WhatsApp-style read ticks.
    """
    # 1. Verify User is a member
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

    if not messages:
        return ChatMessagesListResponse(data=[])

    user_id_str = str(current_user.id)
    message_ids = [m.id for m in messages if m.id]

    # 2. Collect sender IDs and replied-to message IDs
    sender_uuids = set()
    reply_ids = set()

    for m in messages:
        if m.sender_id and m.sender_id != "SYSTEM":
            try:
                sender_uuids.add(uuid.UUID(m.sender_id))
            except (ValueError, TypeError):
                pass
        if m.reply_to_message_id:
            reply_ids.add(m.reply_to_message_id)

    # 3. Bulk fetch replied-to messages in 1 query
    replied_map = {}
    if reply_ids:
        referenced = session.exec(
            select(GroupChatMessage).where(GroupChatMessage.id.in_(reply_ids))
        ).all()
        for rm in referenced:
            replied_map[rm.id] = rm
            if rm.sender_id and rm.sender_id != "SYSTEM":
                try:
                    sender_uuids.add(uuid.UUID(rm.sender_id))
                except (ValueError, TypeError):
                    pass

    # 4. Bulk fetch all sender User profiles in 1 query
    user_map = {}
    if sender_uuids:
        users = session.exec(select(User).where(User.id.in_(sender_uuids))).all()
        user_map = {str(u.id): u for u in users}

    # 5. Bulk fetch read receipts for all messages in this batch in 1 query
    read_receipts = session.exec(
        select(GroupChatReadReceipt.message_id, GroupChatReadReceipt.user_id)
        .where(GroupChatReadReceipt.message_id.in_(message_ids))
    ).all()

    read_by_map = defaultdict(set)
    for mid, uid in read_receipts:
        read_by_map[mid].add(str(uid))

    # 6. Assemble rich ChatMessageItem response
    output: List[ChatMessageItem] = []
    for m in messages:
        is_outgoing = (m.sender_id == user_id_str)
        sender_u = user_map.get(m.sender_id)

        if is_outgoing:
            s_name = "You"
        elif m.sender_id == "SYSTEM":
            s_name = "System"
        else:
            s_name = sender_u.full_name if sender_u and sender_u.full_name else "Member"

        s_phone = sender_u.phone_number if sender_u else None
        s_avatar = sender_u.profile_picture_url if sender_u else None
        s_color = resolve_vibrant_avatar_color(sender_u.avatar_color if sender_u else None, seed=m.sender_id)

        # Read Receipts & Blue Ticks
        readers = read_by_map.get(m.id, set())
        other_readers = readers - {m.sender_id}
        read_cnt = len(other_readers)
        is_read = read_cnt > 0  # Read by someone else!
        is_read_by_me = user_id_str in readers

        # WhatsApp-style tick status
        if is_read:
            tick_status = "READ"  # Double blue ticks
        elif m.status == "DELIVERED":
            tick_status = "DELIVERED"  # Double gray ticks
        else:
            tick_status = "SENT"  # Single gray tick

        # Quoted Reply Preview
        reply_summary = None
        if m.reply_to_message_id and m.reply_to_message_id in replied_map:
            rm = replied_map[m.reply_to_message_id]
            rm_user = user_map.get(rm.sender_id)
            if rm.sender_id == user_id_str:
                rm_sender_name = "You"
            elif rm.sender_id == "SYSTEM":
                rm_sender_name = "System"
            else:
                rm_sender_name = rm_user.full_name if rm_user and rm_user.full_name else "Member"

            rm_preview = rm.message_text
            if not rm_preview and rm.media_type:
                rm_preview = f"📷 {rm.media_type}"

            reply_summary = ReplyToSummary(
                message_id=str(rm.id),
                sender_id=rm.sender_id,
                sender_name=rm_sender_name,
                text=rm_preview,
                media_type=rm.media_type
            )

        output.append(
            ChatMessageItem(
                id=str(m.id),
                client_message_id=m.client_message_id,
                group_id=m.group_id,
                sender_id=m.sender_id,
                sender_name=s_name,
                sender_phone=s_phone,
                sender_avatar_url=s_avatar,
                sender_avatar_color=s_color,
                is_outgoing=is_outgoing,
                message_type=m.message_type,
                message_text=m.message_text,
                media_url=m.media_url,
                media_type=m.media_type,
                media_mime_type=m.media_mime_type,
                media_size_bytes=m.media_size_bytes,
                media_duration_seconds=m.media_duration_seconds,
                media_width=m.media_width,
                media_height=m.media_height,
                aspect_ratio=m.aspect_ratio,
                attachments=m.attachments,
                reply_to=reply_summary,
                reply_to_message_id=str(m.reply_to_message_id) if m.reply_to_message_id else None,
                status=tick_status,
                read_count=read_cnt,
                is_read=is_read,
                is_read_by_me=is_read_by_me,
                created_at=m.created_at,
                updated_at=m.updated_at
            )
        )

    return ChatMessagesListResponse(data=output)

