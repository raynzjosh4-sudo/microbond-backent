import time
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.services.websocket_manager import ws_manager
from .schemas import HeartbeatRequest
from .helpers.format_last_seen import format_last_seen

router = APIRouter()


@router.post("/me/heartbeat", summary="Post User Activity Heartbeat")
async def send_user_heartbeat(
    payload: HeartbeatRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    now_ms = int(time.time() * 1000)

    db_user = session.get(User, current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    db_user.last_seen_at = now_ms
    db_user.is_online = payload.is_online

    session.add(db_user)
    session.commit()
    session.refresh(db_user)

    user_id_str = str(db_user.id)

    if payload.current_group_id:
        event_name = "USER_ONLINE" if payload.is_online else "USER_OFFLINE"
        await ws_manager.broadcast_to_group(
            payload.current_group_id,
            {
                "event_type": event_name,
                "user_id": user_id_str,
                "last_seen_at": now_ms,
                "last_seen_formatted": format_last_seen(
                    now_ms, payload.is_online
                ),
            },
            exclude_user_id=user_id_str,
        )

    return {
        "status": "success",
        "data": {
            "user_id": user_id_str,
            "is_online": db_user.is_online,
            "last_seen_at": db_user.last_seen_at,
            "last_seen_formatted": format_last_seen(
                db_user.last_seen_at, db_user.is_online
            ),
        },
    }
