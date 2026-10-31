import time
import uuid
import importlib

import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool

from app.api.dependencies import get_current_user
from app.core.database import get_session
from app.main import app
from app.api.routes.group.target_savings.schemas.target_savings_group_create_request import (
    TargetSavingsGroupCreateRequest,
)
from app.models.group.group import Group
from app.models.group.core.group_membership import GroupMembership
from app.models.group.settings import GroupGovernanceSettings
from app.models.group.target_savings import TargetSavingsGroupDetails
from app.models.user.user import User
from app.models.user.payout_destination.user_payout_destination import (
    UserPayoutDestination,
)


def valid_request(**overrides):
    payload = {
        "name": "Flexible goal",
        "group_image_url": "https://example.com/group.png",
        "start_date": int(time.time() * 1000),
    }
    payload.update(overrides)
    return payload


def test_target_savings_defaults_are_flexible():
    request = TargetSavingsGroupCreateRequest(**valid_request())

    assert request.allow_target_amount is False
    assert request.allow_target_date is False
    assert request.allow_contribution_schedule is False
    assert request.allow_collection_frequency is False
    assert request.allow_multi_payout is True
    assert request.enable_late_fees is False
    assert request.minimum_kyc_tier == 1


def test_enabled_target_amount_and_date_require_values():
    with pytest.raises(ValidationError, match="target_amount is required"):
        TargetSavingsGroupCreateRequest(
            **valid_request(allow_target_amount=True)
        )

    with pytest.raises(ValidationError, match="target_date is required"):
        TargetSavingsGroupCreateRequest(
            **valid_request(allow_target_date=True)
        )


def test_frequency_requires_schedule_and_positive_interval():
    with pytest.raises(ValidationError, match="requires a contribution schedule"):
        TargetSavingsGroupCreateRequest(
            **valid_request(
                allow_collection_frequency=True,
                collection_frequency_days=7,
            )
        )

    with pytest.raises(ValidationError, match="must be positive"):
        TargetSavingsGroupCreateRequest(
            **valid_request(
                allow_contribution_schedule=True,
                contribution_amount=1000,
                allow_collection_frequency=True,
            )
        )


def test_late_fees_require_a_scheduled_frequency_and_amount():
    with pytest.raises(ValidationError, match="require an enabled contribution frequency"):
        TargetSavingsGroupCreateRequest(
            **valid_request(enable_late_fees=True, late_fee_amount=500)
        )

    request = TargetSavingsGroupCreateRequest(
        **valid_request(
            allow_contribution_schedule=True,
            contribution_amount=1000,
            allow_collection_frequency=True,
            collection_frequency_days=7,
            enable_late_fees=True,
            late_fee_amount=500,
        )
    )
    assert request.enable_late_fees is True


def test_member_cap_requires_an_explicit_positive_limit():
    with pytest.raises(ValidationError, match="Set max_members only"):
        TargetSavingsGroupCreateRequest(
            **valid_request(allow_max_members=True)
        )

    request = TargetSavingsGroupCreateRequest(
        **valid_request(allow_max_members=True, max_members=8)
    )
    assert request.max_members == 8


def test_target_savings_create_persists_group_start_date_and_shared_kyc(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        creator = User(
            id=uuid.uuid4(),
            phone_number="+256700000009",
            full_name="Goal creator",
            kyc_tier=2,
        )
        session.add(creator)
        session.commit()

        app.dependency_overrides[get_session] = lambda: session
        app.dependency_overrides[get_current_user] = lambda: creator
        create_module = importlib.import_module(
            "app.api.routes.group.target_savings.create_target_savings_group"
        )
        monkeypatch.setattr(create_module, "broadcast_system_message_sync", lambda **kwargs: None)
        try:
            start_date = int(time.time() * 1000) + 60_000
            response = TestClient(app).post(
                "/api/v1/groups/target-savings/create",
                json={
                    "name": "Goal savings test",
                    "group_image_url": "https://example.com/group.png",
                    "start_date": start_date,
                    "minimum_kyc_tier": 2,
                    "allow_max_members": True,
                    "max_members": 8,
                    "allow_multi_payout": False,
                },
            )
            assert response.status_code == 200, response.text

            group_id = response.json()["data"]["group_id"]
            group = session.exec(
                select(Group).where(Group.group_id == group_id)
            ).first()
            governance = session.exec(
                select(GroupGovernanceSettings).where(
                    GroupGovernanceSettings.group_id == group_id
                )
            ).one()
            details = session.exec(
                select(TargetSavingsGroupDetails).where(
                    TargetSavingsGroupDetails.group_id == group_id
                )
            ).one()

            assert group is not None
            assert group.start_date == start_date
            assert group.max_members == 8
            assert governance.minimum_kyc_tier == 2
            assert details.minimum_kyc_tier == 2
            assert details.allow_multi_payout is False
            assert details.payout_destination_type == "SINGLE_NOMINATED_ACCOUNT"
        finally:
            app.dependency_overrides.clear()


def test_shared_payout_approval_counts_include_members_who_join_after_proposal(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        users = [
            User(
                id=uuid.uuid4(),
                phone_number=f"+2567000000{index:02d}",
                full_name=f"Goal member {index}",
                kyc_tier=2,
            )
            for index in range(1, 4)
        ]
        session.add_all(users)
        session.commit()

        active_user = {"user": users[0]}
        app.dependency_overrides[get_session] = lambda: session
        app.dependency_overrides[get_current_user] = lambda: active_user["user"]
        create_module = importlib.import_module(
            "app.api.routes.group.target_savings.create_target_savings_group"
        )
        payout_module = importlib.import_module(
            "app.api.routes.group.target_savings.payout_destinations"
        )
        monkeypatch.setattr(create_module, "broadcast_system_message_sync", lambda **kwargs: None)
        monkeypatch.setattr(payout_module, "broadcast_system_message_sync", lambda **kwargs: None)
        client = TestClient(app)
        try:
            response = client.post(
                "/api/v1/groups/target-savings/create",
                json={
                    "name": "Shared payout test",
                    "group_image_url": "https://example.com/group.png",
                    "start_date": int(time.time() * 1000),
                    "allow_multi_payout": False,
                },
            )
            assert response.status_code == 200, response.text
            group_id = response.json()["data"]["group_id"]

            for user in users[1:2]:
                session.add(
                    GroupMembership(
                        membership_id=str(uuid.uuid4()),
                        group_id=group_id,
                        user_id=user.id,
                        status="ACTIVE",
                    )
                )
            session.commit()

            response = client.put(
                f"/api/v1/groups/target-savings/{group_id}/payout-destination",
                json={
                    "provider_name": "Example Bank",
                    "account_type": "BANK_ACCOUNT",
                    "account_number": "123456789",
                    "account_name": "Goal Group",
                },
            )
            assert response.status_code == 200, response.text
            proposal_data = response.json()["data"]
            assert proposal_data["required_count"] == 2
            assert proposal_data["approved_count"] == 0

            response = client.post(
                f"/api/v1/groups/target-savings/{group_id}/payout-destination/approval",
                json={"approved": True},
            )
            assert response.status_code == 200, response.text
            assert response.json()["data"]["approved_count"] == 1
            assert response.json()["data"]["required_count"] == 2

            session.add(
                GroupMembership(
                    membership_id=str(uuid.uuid4()),
                    group_id=group_id,
                    user_id=users[2].id,
                    status="ACTIVE",
                )
            )
            session.commit()

            active_user["user"] = users[2]
            response = client.get(
                f"/api/v1/groups/target-savings/{group_id}/payout-destination"
            )
            assert response.status_code == 200, response.text
            status_data = response.json()["data"]
            assert status_data["approved_count"] == 1
            assert status_data["required_count"] == 3
            assert len(status_data["missing_user_ids"]) == 2
            assert status_data["current_user_approved"] is False

            response = client.post(
                f"/api/v1/groups/target-savings/{group_id}/payout-destination/approval",
                json={"approved": True},
            )
            assert response.status_code == 200, response.text
            assert response.json()["data"]["approved_count"] == 2
            assert response.json()["data"]["required_count"] == 3
        finally:
            app.dependency_overrides.clear()


def test_member_payout_destination_requires_verified_linked_account(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        admin = User(
            id=uuid.uuid4(),
            phone_number="+256700000101",
            full_name="Goal admin",
            kyc_tier=2,
        )
        member = User(
            id=uuid.uuid4(),
            phone_number="+256700000102",
            full_name="Goal member",
            kyc_tier=2,
        )
        session.add_all([admin, member])
        session.commit()

        active_user = {"user": admin}
        app.dependency_overrides[get_session] = lambda: session
        app.dependency_overrides[get_current_user] = lambda: active_user["user"]
        create_module = importlib.import_module(
            "app.api.routes.group.target_savings.create_target_savings_group"
        )
        monkeypatch.setattr(create_module, "broadcast_system_message_sync", lambda **kwargs: None)
        client = TestClient(app)
        try:
            response = client.post(
                "/api/v1/groups/target-savings/create",
                json={
                    "name": "Member payout test",
                    "group_image_url": "https://example.com/group.png",
                    "start_date": int(time.time() * 1000),
                    "allow_multi_payout": True,
                },
            )
            assert response.status_code == 200, response.text
            group_id = response.json()["data"]["group_id"]
            session.add(
                GroupMembership(
                    membership_id=str(uuid.uuid4()),
                    group_id=group_id,
                    user_id=member.id,
                    status="ACTIVE",
                )
            )
            verified_destination = UserPayoutDestination(
                user_id=member.id,
                provider_name="Example Bank",
                account_number="123456789",
                account_name="Goal Member",
                account_type="BANK_ACCOUNT",
                is_verified=True,
            )
            unverified_destination = UserPayoutDestination(
                user_id=member.id,
                provider_name="Other Bank",
                account_number="987654321",
                account_name="Goal Member",
                account_type="BANK_ACCOUNT",
                is_verified=False,
            )
            session.add_all([verified_destination, unverified_destination])
            session.commit()

            active_user["user"] = member
            response = client.get(
                f"/api/v1/groups/target-savings/{group_id}/my-payout-destination"
            )
            assert response.status_code == 200, response.text
            assert response.json()["data"]["destination_required"] is True

            response = client.put(
                f"/api/v1/groups/target-savings/{group_id}/my-payout-destination",
                json={"payout_destination_id": unverified_destination.id},
            )
            assert response.status_code == 400

            response = client.put(
                f"/api/v1/groups/target-savings/{group_id}/my-payout-destination",
                json={"payout_destination_id": verified_destination.id},
            )
            assert response.status_code == 200, response.text

            response = client.get(
                f"/api/v1/groups/target-savings/{group_id}/my-payout-destination"
            )
            assert response.status_code == 200, response.text
            assert response.json()["data"]["destination_required"] is False
            assert response.json()["data"]["payout_destination_id"] == verified_destination.id
        finally:
            app.dependency_overrides.clear()
