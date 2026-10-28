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
from app.models.group.settings import GroupGovernanceSettings
from app.models.group.target_savings import TargetSavingsGroupDetails
from app.models.user.user import User


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
