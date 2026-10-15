import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group, GroupMembership
from app.models.group.chat import GroupChatMessage
from app.models.group.bill_split import BillSplitConfig, BillSplitMemberShare
from .helpers import utc_now as utc_now

router = APIRouter()

@router.post("/{group_id}/remind-defaulters")
def remind_defaulters(
    group_id: str,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Send reminders to members who have not yet settled their assigned bill share.
    """
    membership = db.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == current_user.id
        )
    ).first()
    if not membership or membership.role != "ADMIN":
        raise HTTPException(status_code=403, detail="Only group admins can trigger reminders.")

    group = db.exec(select(Group).where(Group.group_id == group_id)).first()
    config = db.exec(select(BillSplitConfig).where(BillSplitConfig.group_id == group_id)).first()
    if not group or not config:
        raise HTTPException(status_code=404, detail="Bill split group not found.")

    unsettled_shares = db.exec(
        select(BillSplitMemberShare).where(
            BillSplitMemberShare.group_id == group_id,
            BillSplitMemberShare.is_settled == False
        )
    ).all()

    if not unsettled_shares:
        return {
            "status": "success",
            "message": "All members have settled their bill share! No defaulters found.",
            "unsettled_count": 0
        }

    user_ids = [s.user_id for s in unsettled_shares]
    unsettled_users = db.exec(select(User).where(User.id.in_(user_ids))).all()
    user_names = [u.full_name for u in unsettled_users if u.full_name]

    now = utc_now()
    announcement = GroupChatMessage(
        message_id=str(uuid.uuid4()),
        group_id=group_id,
        sender_id=current_user.id,
        message_type="SYSTEM",
        message_text=f"⏰ Payment Reminder: {len(unsettled_shares)} member(s) have pending shares for this bill. Please settle promptly!",
        created_at=now,
    )
    db.add(announcement)
    db.commit()

    return {
        "status": "success",
        "message": f"Reminder posted for {len(unsettled_shares)} pending member(s).",
        "unsettled_count": len(unsettled_shares),
        "unsettled_members": user_names
    }
