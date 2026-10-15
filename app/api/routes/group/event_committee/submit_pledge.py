import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session, select

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.group.group import Group
from app.models.user.user import User
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .schemas import SubmitPledgeRequest
from .helpers import get_event_committee, require_member, now_ms

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/{group_id}/submit-pledge", summary="Member submits a pledge (promise to pay)")
def submit_pledge(
    group_id: str,
    request: SubmitPledgeRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Member records a pledged amount toward the event.
    Increments total_pledged and notifies group chat.
    """
    require_member(group_id, current_user, session)
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    config, settings = get_event_committee(group_id, session)

    if not settings.track_pledges:
        raise HTTPException(status_code=400, detail="Pledge tracking is disabled for this committee.")

    if not settings.is_active:
        raise HTTPException(status_code=400, detail="This committee is closed for pledges and deposits.")

    settings.total_pledged += request.pledged_amount
    settings.updated_at = now_ms()
    session.add(settings)

    try:
        session.commit()
    except Exception as e:
        session.rollback()
        logger.exception(f"Error recording pledge: {e}")
        raise HTTPException(status_code=500, detail="Database error recording pledge.")

    note_text = f" (Note: {request.note})" if request.note else ""
    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"🤝 {current_user.full_name} made a pledge of {request.pledged_amount} {group.currency}{note_text}.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Pledge recorded successfully.",
        "data": {
            "pledged_amount": request.pledged_amount,
            "total_pledged": settings.total_pledged
        }
    }
