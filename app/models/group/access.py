from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, Index, Text, text
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PermissionCatalog(SQLModel, table=True):
    __tablename__ = "permission_catalog"

    permission_code: str = Field(primary_key=True)
    description: str = Field(sa_type=Text)


class GroupRoleGrant(SQLModel, table=True):
    __tablename__ = "group_role_grant"
    __table_args__ = (
        Index(
            "uq_active_group_role_grant",
            "group_id",
            "user_id",
            "role_code",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    role_code: str = Field(index=True)
    granted_by_user_id: UUID = Field(foreign_key="user.id")
    status: str = Field(default="ACTIVE", index=True)
    granted_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    expires_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    revoked_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    revoked_by_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    reason: Optional[str] = Field(default=None, sa_type=Text)


class GroupPermissionGrant(SQLModel, table=True):
    __tablename__ = "group_permission_grant"
    __table_args__ = (
        Index(
            "uq_active_group_permission_grant",
            "group_id",
            "user_id",
            "permission_code",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    group_id: str = Field(foreign_key="group.group_id", index=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    permission_code: str = Field(foreign_key="permission_catalog.permission_code", index=True)
    granted_by_user_id: UUID = Field(foreign_key="user.id")
    status: str = Field(default="ACTIVE", index=True)
    granted_at: datetime = Field(default_factory=utc_now, sa_type=DateTime(timezone=True))
    expires_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    revoked_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
