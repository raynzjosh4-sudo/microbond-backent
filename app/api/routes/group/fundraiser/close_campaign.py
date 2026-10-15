from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .helpers import get_campaign, require_admin, now_ms

router = APIRouter()

@router.post("/{group_id}/close-campaign", summary="Stop accepting donations")
def close_campaign(
    group_id: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Admin closes the campaign — no new donations will be accepted.
    The money is NOT released here. Use release-funds or request-signoff for that.
    """
    require_admin(group_id, current_user, session)
    _, stats = get_campaign(group_id, session)

    if not stats.is_active:
        raise HTTPException(status_code=400, detail="This campaign is already closed.")
    if stats.is_paid_out:
        raise HTTPException(status_code=400, detail="This fundraiser has already paid out.")

    stats.is_active = False
    stats.updated_at = now_ms()
    session.add(stats)
    session.commit()

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=f"{current_user.full_name} has closed this fundraiser. No new donations are being accepted.",
        message_type="SYSTEM_EVENT",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Campaign closed. No more donations will be accepted."
    }
