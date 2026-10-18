import time
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import GroupMembership
from .helpers.format_last_seen import format_last_seen

router = APIRouter()


@router.get(
    "/presence/group/{group_id}",
    summary="Get Presence of All Members in a Group",
)
def get_group_members_presence(
    group_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id,
            GroupMembership.status == "ACTIVE",
        )
    ).first()

    if not membership:
        raise HTTPException(
            status_code=403, detail="You must be an active group member."
        )

    rows = session.exec(
        select(User)
        .join(GroupMembership, GroupMembership.user_id == User.id)
        .where(
            GroupMembership.group_id == group_id,
            GroupMembership.status == "ACTIVE",
        )
    ).all()

    now_ms = int(time.time() * 1000)
    presence_list = []
    online_count = 0

    for u in rows:
        is_active = u.is_online
        if is_active and u.last_seen_at and (now_ms - u.last_seen_at > 180000):
            is_active = False

        if is_active:
            online_count += 1

        from app.services.privacy import can_view_profile_photo
        allow_photo = can_view_profile_photo(
            u, viewer_user_id=current_user.id, shares_group=True
        )

        presence_list.append(
            {
                "user_id": str(u.id),
                "full_name": u.full_name,
                "profile_picture_url": u.profile_picture_url if allow_photo else None,
                "avatar_color": u.avatar_color,
                "is_online": is_active,
                "last_seen_at": u.last_seen_at,
                "last_seen_formatted": format_last_seen(
                    u.last_seen_at, is_active
                ),
            }
        )

    return {
        "status": "success",
        "group_id": group_id,
        "total_members": len(rows),
        "online_count": online_count,
        "members": presence_list,
    }
