from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models.group.core.group_membership import GroupMembership
from app.models.group.access import GroupPermissionGrant, GroupRoleGrant


def grant_role(
    session: Session,
    group_id: str,
    user_id: UUID,
    role_code: str,
    granted_by_user_id: UUID,
) -> GroupRoleGrant:
    existing = session.exec(
        select(GroupRoleGrant).where(
            GroupRoleGrant.group_id == group_id,
            GroupRoleGrant.user_id == user_id,
            GroupRoleGrant.role_code == role_code,
            GroupRoleGrant.status == "ACTIVE",
        )
    ).first()
    if existing is not None:
        return existing

    grant = GroupRoleGrant(
        group_id=group_id,
        user_id=user_id,
        role_code=role_code,
        granted_by_user_id=granted_by_user_id,
        status="ACTIVE",
    )
    session.add(grant)
    return grant


ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "OWNER": frozenset({"*"}),
    "ADMIN": frozenset(
        {
            "INVITE_MEMBERS",
            "MANAGE_ROLES",
            "EDIT_SETTINGS",
            "APPROVE_PAYOUT",
            "SIGN_PAYOUT",
            "MANAGE_MEMBERS",
            "VIEW_REPORTS",
            "MANAGE_GROUP",
            "MANAGE_FINANCES",
            "MANAGE_CHAT",
        }
    ),
    "TREASURER": frozenset(
        {"VIEW_LEDGER", "VIEW_REPORTS", "MANAGE_FINANCES", "APPROVE_PAYOUT"}
    ),
    "SIGNER": frozenset({"SIGN_PAYOUT"}),
    "MODERATOR": frozenset({"MANAGE_CHAT"}),
    "AUDITOR": frozenset({"VIEW_LEDGER", "VIEW_REPORTS"}),
    "LOAN_OFFICER": frozenset({"REVIEW_LOANS"}),
    "MEMBER": frozenset({"VIEW_GROUP", "CHAT"}),
}


def has_permission(
    session: Session,
    actor_id: UUID,
    group_id: str,
    permission_code: str,
) -> bool:
    now = datetime.now(timezone.utc)
    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == actor_id,
            GroupMembership.status == "ACTIVE",
        )
    ).first()
    if membership is None:
        return False

    direct_grant = session.exec(
        select(GroupPermissionGrant).where(
            GroupPermissionGrant.group_id == group_id,
            GroupPermissionGrant.user_id == actor_id,
            GroupPermissionGrant.permission_code == permission_code,
            GroupPermissionGrant.status == "ACTIVE",
        )
    ).all()
    if any(grant.expires_at is None or grant.expires_at > now for grant in direct_grant):
        return True

    role_grants = session.exec(
        select(GroupRoleGrant).where(
            GroupRoleGrant.group_id == group_id,
            GroupRoleGrant.user_id == actor_id,
            GroupRoleGrant.status == "ACTIVE",
        )
    ).all()
    for grant in role_grants:
        if grant.expires_at is not None and grant.expires_at <= now:
            continue
        permissions = ROLE_PERMISSIONS.get(grant.role_code, frozenset())
        if "*" in permissions or permission_code in permissions:
            return True
    return False


def require_permission(
    session: Session,
    actor_user_id: UUID,
    group_id: str,
    permission: str,
) -> None:
    if not has_permission(session, actor_user_id, group_id, permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission required: {permission}.",
        )
