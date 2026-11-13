import importlib.util
from io import StringIO
import uuid
from datetime import datetime, time, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

import app.models.group.access
import app.models.group.core.membership_join_request
import app.models.group.rotating
import app.models.infrastructure
import app.models.user.invite
from app.core.db_idempotency import begin_db_command, complete_db_command
from app.core.db_transaction import transaction
from app.core.token_security import generate_opaque_token, hash_opaque_token
from app.models.group.access import GroupRoleGrant
from app.models.group.core.group import Group
from app.models.group.core.group_membership import GroupMembership
from app.models.group.core.membership_join_request import MembershipJoinRequest
from app.models.group.finance.guarantor_pledge import GuarantorPledge
from app.models.user.core.user import User
from app.services.group.authorization import has_permission
from app.services.group.join_requests import maybe_activate_join_request
from app.utils.money import as_decimal, from_minor_units, quantize_money, to_minor_units
from app.utils.time.api_time import local_datetime, now_utc, require_aware_utc


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        yield db


def test_new_schema_models_create_with_sqlmodel_metadata():
    expected_tables = {
        "invite",
        "membership_join_request",
        "rotatinggroupdetails",
        "rotating_cycle",
        "rotating_daily_collection",
        "rotating_payout",
        "rotating_payout_recipient",
        "rotating_reserve_entry",
        "rotating_turn_swap",
        "group_role_grant",
        "group_permission_grant",
        "permission_catalog",
        "payment_webhook_event",
        "backend_job_execution",
    }
    assert expected_tables <= SQLModel.metadata.tables.keys()
    assert {
        "invite_token_hash",
        "group_public_id",
        "uses_count",
        "accepted_at",
    } <= set(SQLModel.metadata.tables["invite"].columns.keys())
    assert {
        "timezone_name",
        "collection_start_time",
        "collection_end_time",
        "cycle_length_days",
        "recipients_per_cycle",
        "reserve_percentage",
        "updated_at",
    } <= set(SQLModel.metadata.tables["rotatinggroupdetails"].columns.keys())
    assert {
        "uq_user_client_request_id",
        "uq_rotating_cycle_group_number",
        "uq_payment_webhook_provider_event",
        "uq_active_group_role_grant",
        "uq_open_membership_join_request",
    } <= {
        index.name
        for table in SQLModel.metadata.tables.values()
        for index in table.indexes
    }


def test_new_migration_renders_postgresql_unique_indexes():
    migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "d2e3f4a5b6c7_add_api_idempotency_constraints.py"
    )
    spec = importlib.util.spec_from_file_location("api_constraints_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    output = StringIO()
    context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": output},
    )
    with Operations.context(context):
        migration.upgrade()

    rendered_sql = output.getvalue()
    assert "CREATE UNIQUE INDEX IF NOT EXISTS uq_user_client_request_id" in rendered_sql
    assert "uq_active_group_role_grant" in rendered_sql

    join_migration_path = (
        Path(__file__).parents[1]
        / "alembic"
        / "versions"
        / "e3f4a5b6c7d8_add_membership_join_request.py"
    )
    join_spec = importlib.util.spec_from_file_location(
        "membership_join_request_migration",
        join_migration_path,
    )
    assert join_spec is not None and join_spec.loader is not None
    join_migration = importlib.util.module_from_spec(join_spec)
    join_spec.loader.exec_module(join_migration)

    join_output = StringIO()
    join_context = MigrationContext.configure(
        dialect_name="postgresql",
        opts={"as_sql": True, "output_buffer": join_output},
    )
    with Operations.context(join_context):
        join_migration.upgrade()

    assert "CREATE TABLE membership_join_request" in join_output.getvalue()
    assert "uq_open_membership_join_request" in join_output.getvalue()


def test_transaction_commits_or_rolls_back(session: Session):
    user = User(id=uuid.uuid4(), phone_number="+256700000001")
    with transaction(session):
        session.add(user)
    assert session.get(User, user.id) is not None

    failed_user = User(id=uuid.uuid4(), phone_number="+256700000002")
    with pytest.raises(RuntimeError):
        with transaction(session):
            session.add(failed_user)
            session.flush()
            raise RuntimeError("rollback")
    assert session.get(User, failed_user.id) is None


def test_idempotency_returns_the_stored_response(session: Session):
    user = User(id=uuid.uuid4(), phone_number="+256700000003")
    session.add(user)
    session.commit()

    assert begin_db_command(session, user.id, "client-req-1") is None
    complete_db_command(
        session,
        user.id,
        "client-req-1",
        {"result": "created"},
        response_code=201,
    )
    session.commit()

    cached = begin_db_command(session, user.id, "client-req-1")
    assert cached is not None
    assert cached.response_code == 201
    assert cached.response_payload == {"result": "created"}


def test_pending_idempotency_key_cannot_be_replayed(session: Session):
    user = User(id=uuid.uuid4(), phone_number="+256700000004")
    session.add(user)
    session.commit()
    begin_db_command(session, user.id, "client-req-2")
    session.commit()

    with pytest.raises(HTTPException) as exc:
        begin_db_command(session, user.id, "client-req-2")
    assert exc.value.status_code == 409


def test_granted_role_requires_active_membership(session: Session):
    user_id = uuid.uuid4()
    creator_id = uuid.uuid4()
    user = User(id=user_id, phone_number="+256700000005")
    creator = User(id=creator_id, phone_number="+256700000006")
    group = Group(
        group_id="public-group-1",
        name="Group",
        group_image_url="",
        type="STANDARD",
        payment_mode="VOLUNTARY",
        created_by_user_id=creator_id,
    )
    membership = GroupMembership(
        membership_id=str(uuid.uuid4()),
        group_id=group.group_id,
        user_id=user_id,
        status="ACTIVE",
    )
    grant = GroupRoleGrant(
        group_id=group.group_id,
        user_id=user_id,
        role_code="TREASURER",
        granted_by_user_id=creator_id,
        status="ACTIVE",
    )
    session.add_all([user, creator, group, membership, grant])
    session.commit()

    assert has_permission(session, user_id, group.group_id, "APPROVE_PAYOUT")
    membership.status = "LEFT"
    session.add(membership)
    session.commit()
    assert not has_permission(session, user_id, group.group_id, "APPROVE_PAYOUT")


def test_money_and_time_helpers_use_decimal_and_timezone_aware_values():
    assert as_decimal(0.1) + as_decimal(0.2) == Decimal("0.3")
    assert quantize_money("1.005") == Decimal("1.01")
    assert to_minor_units("1234.56", decimal_places=2) == 123456
    assert from_minor_units(123456, decimal_places=2) == Decimal("1234.56")

    utc = local_datetime(
        datetime(2026, 11, 13).date(),
        time(12, 0),
        "Africa/Kampala",
    )
    assert utc == datetime(2026, 11, 13, 9, 0, tzinfo=timezone.utc)
    assert require_aware_utc(now_utc()).utcoffset().total_seconds() == 0
    with pytest.raises(ValueError):
        require_aware_utc(datetime(2026, 11, 13))


def test_opaque_tokens_are_random_and_only_the_hash_is_persistable():
    token = generate_opaque_token()
    token_hash = hash_opaque_token(token)

    assert len(token) >= 32
    assert token_hash != token
    assert hash_opaque_token(token) == token_hash


def test_join_request_waits_for_guarantor_and_admin_before_activation(session: Session):
    creator_id, applicant_id, guarantor_id = (uuid.uuid4() for _ in range(3))
    group = Group(
        group_id="join-workflow-group",
        name="Join workflow",
        group_image_url="",
        type="STANDARD",
        payment_mode="VOLUNTARY",
        created_by_user_id=creator_id,
        member_count=1,
        max_members=2,
    )
    request = MembershipJoinRequest(
        group_id=group.group_id,
        user_id=applicant_id,
        public_status="PENDING_GUARANTOR",
        requires_guarantor=True,
        required_guarantors=1,
        requires_admin_approval=True,
        admin_status="PENDING",
    )
    pledge = GuarantorPledge(
        group_id=group.group_id,
        guarantor_user_id=guarantor_id,
        borrower_user_id=applicant_id,
        maximum_liability_amount=100_000,
        status="PENDING_CONSENT",
    )
    session.add_all(
        [
            User(id=creator_id, phone_number="+256700000021"),
            User(id=applicant_id, phone_number="+256700000022"),
            User(id=guarantor_id, phone_number="+256700000023"),
            group,
            request,
            pledge,
        ]
    )
    session.commit()

    assert not maybe_activate_join_request(session, request, creator_id)
    assert session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group.group_id,
            GroupMembership.user_id == applicant_id,
        )
    ).first() is None

    pledge.status = "ACTIVE"
    session.add(pledge)
    assert not maybe_activate_join_request(session, request, creator_id)
    assert request.public_status == "PENDING_APPROVAL"
    assert session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group.group_id,
            GroupMembership.user_id == applicant_id,
        )
    ).first() is None

    request.admin_status = "APPROVED"
    assert maybe_activate_join_request(session, request, creator_id)
    session.commit()

    membership = session.exec(
        select(GroupMembership).where(
            GroupMembership.group_id == group.group_id,
            GroupMembership.user_id == applicant_id,
        )
    ).first()
    assert membership is not None
    assert membership.status == "ACTIVE"
    assert request.public_status == "APPROVED"
    assert session.get(Group, group.id).member_count == 2
