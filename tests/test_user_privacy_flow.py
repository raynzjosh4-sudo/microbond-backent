import os
import sys
import uuid
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool
from app.main import app
from app.core.database import get_session
from app.api.dependencies import get_current_user
from app.models.user.core.user import User
from app.models.group.group import Group, GroupMembership

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(test_engine)

active_user_id = None

def override_get_session():
    with Session(test_engine) as session:
        yield session

def override_get_current_user():
    with Session(test_engine) as session:
        return session.get(User, active_user_id)


def test_user_privacy_full_flow():
    global active_user_id

    try:
        app.dependency_overrides[get_session] = override_get_session
        app.dependency_overrides[get_current_user] = override_get_current_user
        client = TestClient(app)

        # 1. Seed two test users
        user_alice_id = uuid.uuid4()
        user_bob_id = uuid.uuid4()

        with Session(test_engine) as session:
            alice = User(
                id=user_alice_id,
                phone_number="+256701111111",
                full_name="Alice Privacy",
                profile_picture_url="https://r2.microbond.com/alice.jpg",
                about_status="Alice Secret Bio",
                profile_photo_visibility="EVERYONE",
                about_visibility="EVERYONE",
                group_add_permission="EVERYONE",
            )
            bob = User(
                id=user_bob_id,
                phone_number="+256702222222",
                full_name="Bob Admin",
            )
            session.add(alice)
            session.add(bob)
            session.commit()

        active_user_id = user_alice_id

        # 2. Test GET /api/v1/users/me/privacy
        resp_get = client.get("/api/v1/users/me/privacy")
        assert resp_get.status_code == 200
        data = resp_get.json()
        assert data["profile_photo_visibility"] == "EVERYONE"
        assert data["about_visibility"] == "EVERYONE"
        assert data["group_add_permission"] == "EVERYONE"

        # 3. Test PATCH /api/v1/users/me/privacy to NOBODY
        resp_patch = client.patch(
            "/api/v1/users/me/privacy",
            json={
                "profile_photo_visibility": "Nobody",
                "about_visibility": "Nobody",
                "group_add_permission": "Nobody",
            },
        )
        assert resp_patch.status_code == 200
        patched = resp_patch.json()
        assert patched["profile_photo_visibility"] == "NOBODY"
        assert patched["about_visibility"] == "NOBODY"
        assert patched["group_add_permission"] == "NOBODY"

        # 4. Public phone status lookup (must NOT expose Alice's photo or about status)
        resp_status = client.get("/api/v1/users/+256701111111/status")
        assert resp_status.status_code == 200
        status_data = resp_status.json()
        assert status_data["profile_picture_url"] is None
        assert status_data["about_status"] is None
        assert status_data["full_name"] == "Alice Privacy"

        # 5. Contacts sync lookup (must NOT expose Alice's photo or about status)
        active_user_id = user_bob_id
        resp_sync = client.post(
            "/api/contacts/sync",
            json={"phone_numbers": ["+256701111111"]},
        )
        assert resp_sync.status_code == 200
        contacts_data = resp_sync.json()
        assert len(contacts_data) == 1
        assert contacts_data[0]["profile_picture_url"] is None
        assert contacts_data[0]["about_status"] is None

        # 6. Group add member guard (Bob tries to add Alice directly to a group when Alice has group_add_permission=NOBODY)
        group_id = "test-privacy-group-1"
        with Session(test_engine) as session:
            grp = Group(
                group_id=group_id,
                name="Community Fund",
                group_image_url="https://example.com/group.jpg",
                type="MERRY_GO_ROUND",
                payment_mode="OBLIGATION",
                created_by_user_id=user_bob_id,
                status="ACTIVE",
                member_count=1,
            )
            bob_mem = GroupMembership(
                membership_id=str(uuid.uuid4()),
                group_id=group_id,
                user_id=user_bob_id,
                role="ADMIN",
                status="ACTIVE",
            )
            session.add(grp)
            session.add(bob_mem)
            session.commit()

        resp_add = client.post(
            f"/api/v1/groups/{group_id}/members/add",
            json={"user_id": str(user_alice_id), "role": "MEMBER"},
        )
        assert resp_add.status_code == 403
        assert "privacy settings" in resp_add.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()
