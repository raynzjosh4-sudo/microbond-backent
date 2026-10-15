import os
import sys
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
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

if __name__ == "__main__":
    test_sync_contacts()
