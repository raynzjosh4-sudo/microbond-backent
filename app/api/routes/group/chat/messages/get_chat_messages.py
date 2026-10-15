from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import Optional
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.chat import GroupChatMessage

router = APIRouter()

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
