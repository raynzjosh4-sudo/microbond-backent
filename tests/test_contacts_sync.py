import os
import sys
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlalchemy.pool import StaticPool
from app.main import app
from app.core.database import get_session
from app.models.user.core.user import User

# Setup isolated in-memory test database with StaticPool so all sessions share the same in-memory DB
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(test_engine)

def override_get_session():
    with Session(test_engine) as session:
        yield session

app.dependency_overrides[get_session] = override_get_session
client = TestClient(app)

def test_sync_contacts():
    # 1. Seed dummy user in in-memory SQLite
    with Session(test_engine) as session:
        test_user = User(
            id=uuid.uuid4(),
            phone_number="+256779998877",
            full_name="Grace Namubiru",
            avatar_color="Teal",
            about_status="Building wealth on Microbond",
        )
        session.add(test_user)
        session.commit()

    # 2. Test Empty Request
    resp_empty = client.post("/api/contacts/sync", json={"phone_numbers": []})
    assert resp_empty.status_code == 200
    assert resp_empty.json() == []

    # 3. Test Direct /api/contacts/sync with match and non-match and duplicates
    payload = {
        "phone_numbers": [
            "+256779998877",
            "+256700001122",
            "+256779998877", # duplicate should be deduplicated
            "   "
        ]
    }
    resp_match = client.post("/api/contacts/sync", json=payload)
    assert resp_match.status_code == 200
    data = resp_match.json()
    assert len(data) == 1
    assert data[0]["phone_number"] == "+256779998877"
    assert data[0]["profile_name"] == "Grace Namubiru"
    assert data[0]["avatar_color"] == "Teal"
    assert data[0]["about_status"] == "Building wealth on Microbond"

    # 4. Test versioned endpoint alias /api/v1/contacts/sync
    resp_v1 = client.post("/api/v1/contacts/sync", json=payload)
    assert resp_v1.status_code == 200
    assert len(resp_v1.json()) == 1

    print("SUCCESS: /api/contacts/sync and /api/v1/contacts/sync passed all tests!")

def test_discover_groups():
    from app.models.group.core.group import Group
    from app.models.group.core.group_membership import GroupMembership

    with Session(test_engine) as session:
        # Seed group
        test_group = Group(
            group_id="grp-social-discovery-1",
            name="Kampala Tech Savers",
            description="Tech founders savings circle",
            group_image_url="https://microbond.app/img.png",
            type="MERRY_GO_ROUND",
            payment_mode="OBLIGATION",
            visibility="PUBLIC",
            currency="UGX",
            member_count=5,
            created_by_user_id=uuid.uuid4(),
            status="ACTIVE",
        )
        session.add(test_group)

        # Retrieve user Grace
        grace = session.exec(select(User).where(User.phone_number == "+256779998877")).first()
        membership = GroupMembership(
            membership_id=str(uuid.uuid4()),
            group_id="grp-social-discovery-1",
            user_id=grace.id,
            role="MEMBER",
            status="ACTIVE",
        )
        session.add(membership)
        session.commit()

    # 1. Test discovering groups with Grace's phone number
    payload = {"phone_numbers": ["+256779998877", "+256700000000"]}
    resp = client.post("/api/v1/contacts/discover-groups", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["group_id"] == "grp-social-discovery-1"
    assert data[0]["name"] == "Kampala Tech Savers"
    assert data[0]["mutual_contacts_count"] == 1
    assert len(data[0]["contact_members"]) == 1
    assert data[0]["contact_members"][0]["phone_number"] == "+256779998877"
    assert data[0]["contact_members"][0]["profile_name"] == "Grace Namubiru"

    # 2. Test empty phone numbers returns empty list
    resp_empty = client.post("/api/v1/contacts/discover-groups", json={"phone_numbers": []})
    assert resp_empty.status_code == 200
    assert resp_empty.json() == []

    print("SUCCESS: /api/v1/contacts/discover-groups passed all tests!")

if __name__ == "__main__":
    test_sync_contacts()
    test_discover_groups()

