import unittest
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.models.user.user import User
from app.core.database import get_session


class DummySession:
    """Mock session for isolated unit tests."""
    def __init__(self, user):
        self.user = user

    def get(self, model, user_id):
        if str(self.user.id) == str(user_id):
            return self.user
        return None

    def add(self, obj):
        pass

    def commit(self):
        pass

    def refresh(self, obj):
        pass


class TestLogoutFlow(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.user_id = uuid.uuid4()
        self.phone_number = "+256701112233"
        self.mock_user = User(
            id=self.user_id,
            phone_number=self.phone_number,
            full_name="Logout Test User",
            is_online=True,
            fcm_token="sample_fcm_token_12345",
            is_profile_complete=True,
        )

        self.token = create_access_token(data={"sub": str(self.user_id), "phone": self.phone_number})
        self.headers = {"Authorization": f"Bearer {self.token}"}

        # Override DB session to return our mock user
        self.dummy_session = DummySession(self.mock_user)
        app.dependency_overrides[get_session] = lambda: self.dummy_session

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_logout_success(self):
        # 1. Call Logout endpoint
        response = self.client.post("/api/v1/auth/logout", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "success")
        self.assertFalse(data.get("all_devices"))

        # Verify user model mutation (FCM detached, marked offline)
        self.assertIsNone(self.mock_user.fcm_token)
        self.assertFalse(self.mock_user.is_online)

        # 2. Subsequent request using the revoked token must fail with 401
        second_response = self.client.post("/api/v1/auth/logout", headers=self.headers)
        self.assertEqual(second_response.status_code, 401)
        self.assertIn("terminated", second_response.json().get("detail", "").lower())

    def test_logout_all_devices(self):
        token_a = create_access_token(data={"sub": str(self.user_id), "phone": self.phone_number})
        token_b = create_access_token(data={"sub": str(self.user_id), "phone": self.phone_number})

        # Logout of all devices using token_a
        headers_a = {"Authorization": f"Bearer {token_a}"}
        response = self.client.post("/api/v1/auth/logout", headers=headers_a, json={"all_devices": True})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("all_devices"))

        # Both token_a and token_b should now be rejected
        headers_b = {"Authorization": f"Bearer {token_b}"}
        res_b = self.client.post("/api/v1/auth/logout", headers=headers_b)
        self.assertEqual(res_b.status_code, 401)

    def test_logout_aliases_and_no_body(self):
        token = create_access_token(data={"sub": str(self.user_id), "phone": self.phone_number})
        headers = {"Authorization": f"Bearer {token}"}

        # Calling unversioned alias /auth/logout without a body
        res = self.client.post("/auth/logout", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("status"), "success")


if __name__ == "__main__":
    unittest.main()
