import time
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from .helpers.format_last_seen import format_last_seen

router = APIRouter()


@router.get(
    "/presence/{target_user_id}",
    summary="Get Target User Presence & Last Seen",
)
def get_user_presence(
    target_user_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    try:
        target_uuid = uuid.UUID(target_user_id)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid user UUID format."
        )

    if target_uuid != current_user.id:
        my_groups = session.exec(
            select(GroupMembership.group_id).where(
                GroupMembership.user_id == current_user.id,
                GroupMembership.status == "ACTIVE",
            )
        ).all()

        target_member = session.exec(
            select(GroupMembership).where(
                GroupMembership.user_id == target_uuid,
                GroupMembership.status == "ACTIVE",
                GroupMembership.group_id.in_(my_groups),
            )
        ).first()

        if not target_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view the activity of members you share an active group with.",
            )

    target_user = session.get(User, target_uuid)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found.")

    now_ms = int(time.time() * 1000)
    is_active = target_user.is_online
    if (
        is_active
        and target_user.last_seen_at
        and (now_ms - target_user.last_seen_at > 180000)
    ):
        is_active = False

    return {
        "status": "success",
        "data": {
            "user_id": str(target_user.id),
            "full_name": target_user.full_name,
            "is_online": is_active,
            "last_seen_at": target_user.last_seen_at,
            "last_seen_formatted": format_last_seen(
                target_user.last_seen_at, is_active
            ),
        },
    }
