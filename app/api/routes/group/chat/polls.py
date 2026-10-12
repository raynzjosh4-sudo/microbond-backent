from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from sqlmodel import Session, select
import json
import time
import uuid

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.models.group.chat import GroupPoll, GroupPollVote
from app.api.routes.group.chat.messages import broadcast_system_message_sync

router = APIRouter(prefix="/api/v1/groups", tags=["Group Chat Polls"])

class CreatePollRequest(BaseModel):
    question: str = Field(..., max_length=500)
    options: list[str] = Field(..., min_length=2, max_length=10)
    poll_type: str = Field(default="CUSTOM")
    duration_hours: int = Field(default=24)

class VoteRequest(BaseModel):
    selected_option: str = Field(...)

@router.post("/{group_id}/chat/polls", summary="Create a new poll in the group")
def create_poll(
    group_id: str,
    request: CreatePollRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # 1. Verify membership
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    
    if not membership:
        raise HTTPException(status_code=403, detail="You must be an active member to create polls.")

    # 2. Create Poll
    expires_at = int(time.time() * 1000) + (request.duration_hours * 3600 * 1000)
    new_poll = GroupPoll(
        group_id=group_id,
        creator_id=str(current_user.id),
        question=request.question,
        options=json.dumps(request.options),
        poll_type=request.poll_type,
        expires_at=expires_at
    )
    
    session.add(new_poll)
    session.commit()
    session.refresh(new_poll)
    
    # 3. Broadcast to chat
    # We send a special 'VOTE' message containing the poll ID so the UI renders a poll card
    poll_data = new_poll.model_dump(mode="json")
    broadcast_system_message_sync(
        group_id=group_id,
        message_text=json.dumps({"poll_id": str(new_poll.id), "question": new_poll.question, "options": request.options}),
        message_type="VOTE",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )
    
    return {"status": "success", "data": poll_data}

@router.post("/{group_id}/chat/polls/{poll_id}/vote", summary="Vote on a poll")
def vote_on_poll(
    group_id: str,
    poll_id: uuid.UUID,
    request: VoteRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    # 1. Verify Poll exists
    poll = session.get(GroupPoll, poll_id)
    if not poll or poll.group_id != group_id:
        raise HTTPException(status_code=404, detail="Poll not found")
        
    if poll.status != "OPEN" or poll.expires_at < int(time.time() * 1000):
        raise HTTPException(status_code=400, detail="This poll is closed or expired.")

    valid_options = json.loads(poll.options)
    if request.selected_option not in valid_options:
        raise HTTPException(status_code=400, detail="Invalid option selected.")

    # 2. Verify Membership
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    
    if not membership:
        raise HTTPException(status_code=403, detail="You must be an active member to vote.")

    # 3. Record or Update Vote
    existing_vote = session.exec(
        select(GroupPollVote).where(
            GroupPollVote.poll_id == poll_id,
            GroupPollVote.user_id == current_user.id
        )
    ).first()
    
    if existing_vote:
        existing_vote.selected_option = request.selected_option
        session.add(existing_vote)
    else:
        new_vote = GroupPollVote(
            poll_id=poll_id,
            user_id=current_user.id,
            selected_option=request.selected_option
        )
        session.add(new_vote)
        
    session.commit()
    
    # 4. Broadcast a silent real-time update to update the UI vote counts
    from app.services.websocket_manager import ws_manager
    background_tasks.add_task(
        ws_manager.broadcast_to_group,
        group_id,
        {
            "event_type": "POLL_VOTE_UPDATE",
            "poll_id": str(poll_id)
        }
    )

    return {"status": "success", "message": "Vote recorded."}
