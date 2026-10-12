from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from typing import Optional, List
from datetime import datetime, timezone
import time
import uuid

from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from app.services.websocket_manager import ws_manager

router = APIRouter(prefix="/api/v1/users", tags=["Users Presence & Activity"])

class HeartbeatRequest(BaseModel):
    is_online: bool = Field(default=True, description="Whether user is currently actively viewing the app")
    current_group_id: Optional[str] = Field(default=None, description="Optional active group chat screen ID")

class UserPresenceResponse(BaseModel):
    user_id: str
    full_name: Optional[str]
    is_online: bool
    last_seen_at: Optional[int]
    last_seen_formatted: str

def format_last_seen(last_seen_ms: Optional[int], is_online: bool) -> str:
    """Produces human-readable last seen strings (e.g., 'Online', 'Active 5m ago', 'Active 2h ago')."""
    if is_online:
        return "Online"
    if not last_seen_ms:
        return "Offline"
    
    diff_sec = max(0, int((time.time() * 1000 - last_seen_ms) / 1000))
    if diff_sec < 60:
        return "Active just now"
    elif diff_sec < 3600:
        mins = diff_sec // 60
        return f"Active {mins}m ago"
    elif diff_sec < 86400:
        hours = diff_sec // 3600
        return f"Active {hours}h ago"
    else:
        days = diff_sec // 86400
        return f"Active {days}d ago"

@router.post("/me/heartbeat", summary="Post User Activity Heartbeat")
async def send_user_heartbeat(
    payload: HeartbeatRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Periodic heartbeat from client app (called e.g., every 30-60 seconds or on app background/foreground):
    - Updates `last_seen_at` (epoch ms)
    - Updates `is_online` status
    - If user enters background, toggles `is_online: false`
    - Broadcasts presence state to user's active groups via WebSocket
    """
    now_ms = int(time.time() * 1000)

    db_user = session.get(User, current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    previous_online = db_user.is_online
    db_user.last_seen_at = now_ms
    db_user.is_online = payload.is_online

    session.add(db_user)
    session.commit()
    session.refresh(db_user)

    user_id_str = str(db_user.id)

    # If online status changed or active in a group, broadcast presence event
    if payload.current_group_id:
        event_name = "USER_ONLINE" if payload.is_online else "USER_OFFLINE"
        await ws_manager.broadcast_to_group(
            payload.current_group_id,
            {
                "event_type": event_name,
                "user_id": user_id_str,
                "last_seen_at": now_ms,
                "last_seen_formatted": format_last_seen(now_ms, payload.is_online)
            },
            exclude_user_id=user_id_str
        )

    return {
        "status": "success",
        "data": {
            "user_id": user_id_str,
            "is_online": db_user.is_online,
            "last_seen_at": db_user.last_seen_at,
            "last_seen_formatted": format_last_seen(db_user.last_seen_at, db_user.is_online)
        }
    }

@router.get("/presence/{target_user_id}", summary="Get Target User Presence & Last Seen")
def get_user_presence(
    target_user_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves the online status and human-readable last-seen state of a user.
    Enforces privacy by ensuring the requester shares at least one mutual active group.
    """
    try:
        target_uuid = uuid.UUID(target_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user UUID format.")

    # Check mutual group membership (or self)
    if target_uuid != current_user.id:
        my_groups = session.exec(
            select(GroupMembership.group_id).where(
                GroupMembership.user_id == current_user.id,
                GroupMembership.status == "ACTIVE"
            )
        ).all()

        target_member = session.exec(
            select(GroupMembership).where(
                GroupMembership.user_id == target_uuid,
                GroupMembership.status == "ACTIVE",
                GroupMembership.group_id.in_(my_groups)
            )
        ).first()

        if not target_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view the activity of members you share an active group with."
            )

    target_user = session.get(User, target_uuid)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")

    # If last seen is older than 3 minutes, treat as offline even if socket didn't cleanly disconnect
    now_ms = int(time.time() * 1000)
    is_active = target_user.is_online
    if is_active and target_user.last_seen_at and (now_ms - target_user.last_seen_at > 180000):
        is_active = False

    return {
        "status": "success",
        "data": {
            "user_id": str(target_user.id),
            "full_name": target_user.full_name,
            "is_online": is_active,
            "last_seen_at": target_user.last_seen_at,
            "last_seen_formatted": format_last_seen(target_user.last_seen_at, is_active)
        }
    }

@router.get("/presence/group/{group_id}", summary="Get Presence of All Members in a Group")
def get_group_members_presence(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Batch returns online status and last-seen timestamps for all active members in a specific group.
    Ideal for chat headers (e.g. showing '5 online' or avatar activity dots).
    """
    # Verify current user is a member
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()

    if not membership:
        raise HTTPException(status_code=403, detail="You must be an active group member.")

    # Fetch all active members joined with their User presence
    rows = session.exec(
        select(User).join(GroupMembership, GroupMembership.user_id == User.id).where(
            GroupMembership.group_id == group_id,
            GroupMembership.status == "ACTIVE"
        )
    ).all()

    now_ms = int(time.time() * 1000)
    presence_list = []
    online_count = 0

    for u in rows:
        is_active = u.is_online
        # Timeout safety (3 min)
        if is_active and u.last_seen_at and (now_ms - u.last_seen_at > 180000):
            is_active = False

        if is_active:
            online_count += 1

        presence_list.append({
            "user_id": str(u.id),
            "full_name": u.full_name,
            "profile_picture_url": u.profile_picture_url,
            "avatar_color": u.avatar_color,
            "is_online": is_active,
            "last_seen_at": u.last_seen_at,
            "last_seen_formatted": format_last_seen(u.last_seen_at, is_active)
        })

    return {
        "status": "success",
        "group_id": group_id,
        "total_members": len(rows),
        "online_count": online_count,
        "members": presence_list
    }
