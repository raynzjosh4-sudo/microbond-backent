import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlmodel import Session

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.chat import GroupPoll
from app.api.routes.group.chat.messages import broadcast_system_message_sync
from .schemas import RequestSignoffBody
from .helpers import get_campaign, require_admin, now_ms

router = APIRouter()

@router.post("/{group_id}/request-signoff", summary="Ask signers to approve the money release")
def request_signoff(
    group_id: str,
    request: RequestSignoffBody,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Only used when require_multi_signoff is True.
    Creates a group vote (poll) so the required signers can approve releasing the money.
    """
    require_admin(group_id, current_user, session)
    config, stats = get_campaign(group_id, session)

    if not config.require_multi_signoff:
        raise HTTPException(
            status_code=400,
            detail="This fundraiser does not require multi-signoff. Use release-funds directly."
        )
    if stats.is_paid_out:
        raise HTTPException(status_code=400, detail="This fundraiser has already paid out.")

    current_time_ms = now_ms()
    expires_at = current_time_ms + (48 * 3600 * 1000)  # 48-hour voting window

    poll = GroupPoll(
        group_id=group_id,
        creator_id=current_user.id,
        question=f"Approve releasing all collected funds? Reason: {request.reason}",
        options=json.dumps(["Approve Release", "Do Not Release Yet"]),
        poll_type="FUND_RELEASE",
        status="OPEN",
        expires_at=expires_at,
        created_at=current_time_ms
    )
    session.add(poll)
    session.commit()
    session.refresh(poll)

    broadcast_system_message_sync(
        group_id=group_id,
        message_text=json.dumps({
            "poll_id": str(poll.id),
            "question": poll.question,
            "options": ["Approve Release", "Do Not Release Yet"],
            "signoff_count_required": config.signoff_count_required
        }),
        message_type="VOTE",
        sender_id=str(current_user.id),
        session=session,
        background_tasks=background_tasks
    )

    return {
        "status": "success",
        "message": "Signoff request sent to the group chat.",
        "data": {
            "poll_id": str(poll.id),
            "signoff_count_required": config.signoff_count_required,
            "expires_at": poll.expires_at
        }
    }
