from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models.group.group import Group


def get_group_by_public_id(session: Session, public_group_id: str) -> Group:
    group = session.exec(
        select(Group).where(Group.group_id == public_group_id)
    ).first()
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Group not found.",
        )
    return group
