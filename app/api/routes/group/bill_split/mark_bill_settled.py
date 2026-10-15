import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.chat import GroupChatMessage
from app.models.group.bill_split import BillSplitOperationalSettings
from .helpers import utc_now as utc_now

router = APIRouter()

@router.post("/{group_id}/mark-settled")
def mark_bill_settled(
    group_id: str,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Manually mark a bill as settled and close the split group (Admin only).
    """
    membership = db.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    if not membership or membership.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only group admins can mark the bill settled.")

    group = db.exec(select(Group).where(Group.group_id == group_id)).first()
    ops = db.exec(select(BillSplitOperationalSettings).where(BillSplitOperationalSettings.group_id == group_id)).first()
    if not group or not ops:
        raise HTTPException(status_code=404, detail="Bill split group not found.")

    now = utc_now()
    ops.is_settled = True
    ops.settled_at = now
    ops.updated_at = now
    db.add(ops)

    announcement = GroupChatMessage(
        message_id=str(uuid.uuid4()),
        group_id=group_id,
        sender_id=current_user.id,
        message_type="SYSTEM",
        message_text=f"🏁 Bill Closed: {current_user.full_name} marked this bill as settled.",
        created_at=now,
    )
    db.add(announcement)

    db.commit()

    return {
        "status": "success",
        "message": "Bill has been marked as settled.",
        "settled_at": now
    }
