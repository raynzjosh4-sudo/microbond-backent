import time
from fastapi import HTTPException
from sqlmodel import Session, select

from app.models.group.group import GroupMembership
from app.models.user.user import User
from app.models.group.long_term import FundraiserCampaignConfig, FundraiserLiveStats

def now_ms() -> int:
    return int(time.time() * 1000)

def get_campaign(group_id: str, session: Session):
    config = session.exec(
        select(FundraiserCampaignConfig).where(FundraiserCampaignConfig.group_id == group_id)
    ).first()
    stats = session.exec(
        select(FundraiserLiveStats).where(FundraiserLiveStats.group_id == group_id)
    ).first()
    if not config or not stats:
        raise HTTPException(status_code=404, detail="Fundraiser details not found for this group.")
    return config, stats

def require_admin(group_id: str, user: User, session: Session):
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user.id,
            GroupMembership.role == "ADMIN",
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="Only the group admin can do this.")
    return membership

def require_member(group_id: str, user: User, session: Session):
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user.id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(status_code=403, detail="You must be an active member of this group.")
    return membership
