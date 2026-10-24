import uuid
import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.user import User
from app.models.group.group import Group
from app.services.group.group_auth_service import (
    evaluate_group_creation_permissions,
    get_permitted_group_creation_types,
    is_unrestricted_group_creator,
    SavingsGroupType,
)


@pytest.fixture(name="db_session")
def db_session_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_is_unrestricted_group_creator_matcher():
    # Various phone formats for the user
    user_e164 = User(phone_number="+256704903741")
    user_plain = User(phone_number="256704903741")
    user_local = User(phone_number="0704903741")
    user_spaces = User(phone_number=" +256 704 903 741 ")
    user_normal = User(phone_number="+256701234567")

    assert is_unrestricted_group_creator(user_e164) is True
    assert is_unrestricted_group_creator(user_plain) is True
    assert is_unrestricted_group_creator(user_local) is True
    assert is_unrestricted_group_creator(user_spaces) is True
    assert is_unrestricted_group_creator(user_normal) is False
    assert is_unrestricted_group_creator(None) is False


def test_unrestricted_user_evaluation_and_creation(db_session: Session, monkeypatch):
    import app.api.routes.group.chat.messages.helpers.messages_helpers as mh
    monkeypatch.setattr(mh, "notify_all_group_members", lambda **kwargs: None)
    # Create superuser with KYC Tier 0, trust score 0, unverified
    super_user = User(
        id=uuid.uuid4(),
        phone_number="256704903741",
        full_name="Super Boss",
        kyc_tier=0,
        trust_score=0,
        is_verified=False,
    )
    db_session.add(super_user)
    
    # Pre-seed 6 active groups owned by super_user to simulate exceeding limits & running groups
    for i in range(6):
        db_session.add(Group(
            group_id=f"super_active_group_{i}",
            name=f"Existing Group {i}",
            group_image_url="",
            type="GOAL_SAVINGS",
            payment_mode="VOLUNTARY",
            created_by_user_id=super_user.id,
            total_balance=500000,
            member_count=3,
            status="ACTIVE"
        ))
    db_session.commit()

    # 1. Check evaluate_group_creation_permissions
    eval_res = evaluate_group_creation_permissions(db_session, super_user.id)
    all_enums = list(SavingsGroupType)
    assert len(eval_res["allowed_groups"]) == len(all_enums)
    for g in all_enums:
        assert g.value in eval_res["allowed_groups"]

    permitted = get_permitted_group_creation_types(db_session, super_user.id)
    assert len(permitted) == len(all_enums)

    # 2. Check unified create API with super_user
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: super_user
    client = TestClient(app)

    # Can create MERRY_GO_ROUND (normally requires KYC Tier 3, high trust, health grades)
    resp = client.post("/api/v1/groups/create", json={
        "name": "Super Boss Rotating Circle",
        "description": "Unlimited creation circle",
        "type": "MERRY_GO_ROUND",
        "payment_mode": "OBLIGATION",
        "visibility": "PUBLIC",
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "success"

    # Can create ASSOCIATION_DUES
    resp_ad = client.post("/api/v1/groups/create", json={
        "name": "Super Boss Association",
        "description": "Alumni and dues",
        "type": "ASSOCIATION_DUES",
        "payment_mode": "OBLIGATION",
        "visibility": "PRIVATE",
    })
    assert resp_ad.status_code == 200, resp_ad.text
    assert resp_ad.json()["status"] == "success"

    # Can create BILL_SPLIT
    resp_bs = client.post("/api/v1/groups/create", json={
        "name": "Dinner Split Unlimited",
        "description": "Super bill split",
        "type": "BILL_SPLIT",
        "payment_mode": "OBLIGATION",
    })
    assert resp_bs.status_code == 200, resp_bs.text
    assert resp_bs.json()["status"] == "success"

    # 3. Check /me/allowed-groups route returns all groups
    resp_allowed = client.get("/api/v1/users/me/allowed-groups")
    assert resp_allowed.status_code == 200, resp_allowed.text
    allowed_data = resp_allowed.json()
    assert len(allowed_data["allowed_groups"]) == len(all_enums)

    app.dependency_overrides.clear()
