import time
from fastapi import HTTPException
from sqlmodel import Session, select
from app.models.group.group import GroupMembership
from app.models.user.user import User
from app.models.group.investment_association import InvestmentClubConfig, InvestmentClubOperationalSettings

def now_ms() -> int:
    return int(time.time() * 1000)

def get_club(group_id: str, session: Session):
    config = session.exec(
        select(InvestmentClubConfig).where(InvestmentClubConfig.group_id == group_id)
    ).first()
    settings = session.exec(
        select(InvestmentClubOperationalSettings).where(InvestmentClubOperationalSettings.group_id == group_id)
    ).first()
    if not config or not settings:
        raise HTTPException(status_code=404, detail="Investment club configuration not found for this group.")
    return config, settings

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
        raise HTTPException(status_code=403, detail="Only the club admin/chairperson can perform this action.")
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
        raise HTTPException(status_code=403, detail="You must be an active member of this investment club.")
    return membership
