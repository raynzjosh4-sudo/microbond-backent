import uuid
from fastapi import HTTPException, status
from sqlmodel import Session, select
from app.models.group.group import Group, GroupMembership

VALID_ROLES = {"MEMBER", "TREASURER", "ADMIN", "MODERATOR"}

def verify_admin(session: Session, group_id: str, user_id: uuid.UUID) -> tuple[Group, GroupMembership]:
    """Helper verifying caller is an ADMIN of the group."""
    group = session.exec(select(Group).where(Group.group_id == group_id)).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found.")

    caller_membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user_id,
            GroupMembership.status == "ACTIVE"
        )
    ).first()

    if not caller_membership or caller_membership.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrative privileges required. Only group Admins can perform member moderation."
        )

    return group, caller_membership
