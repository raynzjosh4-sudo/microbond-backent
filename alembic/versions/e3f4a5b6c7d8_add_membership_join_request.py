"""Add an explicit, auditable group-joining workflow.

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-11-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, Sequence[str], None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "membership_join_request",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_id", sa.String(), nullable=False),
        sa.Column("invite_id", sa.Integer(), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_status", sa.String(), nullable=False),
        sa.Column("guarantor_status", sa.String(), nullable=False),
        sa.Column("voting_status", sa.String(), nullable=False),
        sa.Column("admin_status", sa.String(), nullable=False),
        sa.Column("requires_guarantor", sa.Boolean(), nullable=False),
        sa.Column("required_guarantors", sa.Integer(), nullable=False),
        sa.Column("requires_admin_approval", sa.Boolean(), nullable=False),
        sa.Column("required_votes", sa.Integer(), nullable=False),
        sa.Column("approved_votes", sa.Integer(), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("kyc_submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["group.group_id"]),
        sa.ForeignKeyConstraint(["invite_id"], ["invite.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_membership_join_request_group_id",
        "membership_join_request",
        ["group_id"],
    )
    op.create_index(
        "ix_membership_join_request_invite_id",
        "membership_join_request",
        ["invite_id"],
    )
    op.create_index(
        "ix_membership_join_request_user_id",
        "membership_join_request",
        ["user_id"],
    )
    op.create_index(
        "ix_membership_join_request_public_status",
        "membership_join_request",
        ["public_status"],
    )
    op.create_index(
        "uq_open_membership_join_request",
        "membership_join_request",
        ["group_id", "user_id"],
        unique=True,
        postgresql_where=sa.text(
            "public_status NOT IN ('APPROVED', 'REJECTED', 'CANCELLED', 'EXPIRED')"
        ),
    )
    op.execute(
        """
        INSERT INTO membership_join_request (
            id, group_id, user_id, public_status, guarantor_status,
            voting_status, admin_status, requires_guarantor,
            required_guarantors, requires_admin_approval, required_votes,
            approved_votes, submitted_at, created_at, updated_at
        )
        SELECT
            gen_random_uuid(),
            gm.group_id,
            gm.user_id,
            gm.status,
            CASE
                WHEN gm.status = 'PENDING_GUARANTOR' THEN 'PENDING'
                ELSE 'NOT_REQUIRED'
            END,
            'NOT_REQUIRED',
            CASE
                WHEN COALESCE(gs.requires_admin_approval, FALSE) THEN 'PENDING'
                ELSE 'NOT_REQUIRED'
            END,
            gm.status = 'PENDING_GUARANTOR',
            CASE
                WHEN gm.status = 'PENDING_GUARANTOR'
                    THEN GREATEST(COALESCE(gs.guarantor_count, 1), 1)
                ELSE 0
            END,
            COALESCE(gs.requires_admin_approval, FALSE),
            0,
            0,
            now(),
            now(),
            now()
        FROM groupmembership AS gm
        LEFT JOIN groupgovernancesettings AS gs
            ON gs.group_id = gm.group_id
        WHERE gm.status IN ('PENDING_APPROVAL', 'PENDING_GUARANTOR')
          AND NOT EXISTS (
              SELECT 1
              FROM membership_join_request AS existing
              WHERE existing.group_id = gm.group_id
                AND existing.user_id = gm.user_id
                AND existing.public_status NOT IN (
                    'APPROVED', 'REJECTED', 'CANCELLED', 'EXPIRED'
                )
          )
        """
    )
    op.execute(
        """
        WITH legacy_roles AS (
            SELECT DISTINCT
                gm.group_id,
                gm.user_id,
                upper(trim(gm.role)) AS role_code,
                g.created_by_user_id AS granted_by_user_id
            FROM groupmembership AS gm
            JOIN "group" AS g ON g.group_id = gm.group_id
            WHERE gm.status = 'ACTIVE'
              AND upper(trim(gm.role)) IN (
                  'OWNER', 'ADMIN', 'TREASURER', 'SIGNER',
                  'MODERATOR', 'AUDITOR', 'LOAN_OFFICER', 'MEMBER'
              )
        )
        INSERT INTO group_role_grant (
            id, group_id, user_id, role_code, granted_by_user_id,
            status, granted_at, reason
        )
        SELECT
            gen_random_uuid(),
            legacy.group_id,
            legacy.user_id,
            legacy.role_code,
            legacy.granted_by_user_id,
            'ACTIVE',
            now(),
            'API_ROLE_BACKFILL'
        FROM legacy_roles AS legacy
        WHERE NOT EXISTS (
            SELECT 1
            FROM group_role_grant AS grant_row
            WHERE grant_row.group_id = legacy.group_id
              AND grant_row.user_id = legacy.user_id
              AND grant_row.role_code = legacy.role_code
              AND grant_row.status = 'ACTIVE'
        )
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM group_role_grant WHERE reason = 'API_ROLE_BACKFILL'"
    )
    op.drop_table("membership_join_request")
