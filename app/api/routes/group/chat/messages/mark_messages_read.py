import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.chat import GroupChatMessage, GroupChatReadReceipt
from app.utils.time.now_epoch_ms import now_epoch_ms
from app.services.websocket_manager import ws_manager
from .schemas import MarkMessagesReadRequest, MarkMessagesReadResponse

router = APIRouter()

@router.post(
    "/{group_id}/chat/messages/read",
    response_model=MarkMessagesReadResponse,
    summary="Mark group chat messages as read",
    description="Marks specified messages (or all unread incoming messages) as read by the current user, recording read receipts and broadcasting live blue ticks."
)
async def mark_messages_read(
    group_id: str,
    payload: Optional[MarkMessagesReadRequest] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Records read receipts for incoming messages.
    Triggers double blue ticks for senders in the group.
    """
    user_id_str = str(current_user.id)

    # 1. Verify User is an active group member
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()

    if not membership:
        raise HTTPException(status_code=403, detail="You must be a member of this group.")

    # 2. Determine target messages
    requested_ids = payload.message_ids if payload and payload.message_ids else None
    
    if requested_ids:
        valid_uuids = []
        for mid in requested_ids:
            try:
                valid_uuids.append(uuid.UUID(str(mid)))
            except (ValueError, TypeError):
                continue
                
        if not valid_uuids:
            return MarkMessagesReadResponse(
                status="success",
                group_id=group_id,
                marked_count=0,
                read_at=now_epoch_ms()
            )

        candidate_messages = session.exec(
            select(GroupChatMessage).where(
                GroupChatMessage.group_id == group_id,
                GroupChatMessage.id.in_(valid_uuids),
                GroupChatMessage.is_deleted == False,
                GroupChatMessage.sender_id != user_id_str
            )
        ).all()
    else:
        # Mark all incoming messages in group that aren't yet read by current user
        candidate_messages = session.exec(
            select(GroupChatMessage).where(
                GroupChatMessage.group_id == group_id,
                GroupChatMessage.is_deleted == False,
                GroupChatMessage.sender_id != user_id_str
            )
        ).all()

    if not candidate_messages:
        return MarkMessagesReadResponse(
            status="success",
            group_id=group_id,
            marked_count=0,
            read_at=now_epoch_ms()
        )

    cand_ids = [m.id for m in candidate_messages if m.id]

    # 3. Find existing read receipts for this user
    existing_receipts = session.exec(
        select(GroupChatReadReceipt.message_id).where(
            GroupChatReadReceipt.message_id.in_(cand_ids),
            GroupChatReadReceipt.user_id == user_id_str
        )
    ).all()
    already_read_set = set(existing_receipts)

    # 4. Insert new receipts for unread messages
    now_ms = now_epoch_ms()
    newly_read_uuids = []
    for m in candidate_messages:
        if m.id not in already_read_set:
            receipt = GroupChatReadReceipt(
                message_id=m.id,
                user_id=user_id_str,
                read_at=now_ms
            )
            session.add(receipt)
            newly_read_uuids.append(m.id)

    if newly_read_uuids:
        session.commit()

        # 5. Broadcast live MESSAGE_READ events to group members (excludes reader)
        for mid in newly_read_uuids:
            try:
                await ws_manager.broadcast_to_group(
                    group_id,
                    {
                        "event_type": "MESSAGE_READ",
                        "message_id": str(mid),
                        "user_id": user_id_str,
                        "group_id": group_id,
                        "read_at": now_ms
                    },
                    exclude_user_id=user_id_str
                )
            except Exception as e:
                pass

    return MarkMessagesReadResponse(
        status="success",
        group_id=group_id,
        marked_count=len(newly_read_uuids),
        read_at=now_ms
    )
