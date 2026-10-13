from fastapi import HTTPException
from sqlmodel import Session, select
from app.models.user.user import User
from app.models.group.group import GroupMembership

def require_group_admin(group_id: str, user: User, session: Session) -> GroupMembership:
    """Verifies that the user is an active ADMIN or creator in the specified group."""
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user.id,
            GroupMembership.role == "ADMIN",
            GroupMembership.status == "ACTIVE"
        )
    ).first()
    if not membership:
        raise HTTPException(
            status_code=403, 
            detail="Only an active group administrator can perform this action."
        )
    return membership
