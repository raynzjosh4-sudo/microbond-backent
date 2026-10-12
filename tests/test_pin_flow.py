import unittest
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import hash_pin, create_access_token
from app.models.user.user import User
from app.api.dependencies import get_current_user, require_telecom_kyc_guard
import uuid

class TestAppPinFlow(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.test_user_id = uuid.uuid4()
        self.test_phone = "+256701234567"
        self.plain_pin = "1234"
        self.hashed_pin = hash_pin(self.plain_pin)
        
        self.mock_user = User(
            id=self.test_user_id,
            phone_number=self.test_phone,
            full_name="Test User",
            hashed_pin=self.hashed_pin,
            is_profile_complete=True,
            kyc_status="VERIFIED",
            kyc_tier=2
        )
        
        self.token = create_access_token(data={"sub": str(self.test_user_id), "phone": self.test_phone})
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def test_verify_pin_success(self):
        app.dependency_overrides[get_current_user] = lambda: self.mock_user

        response = self.client.post(
            "/pin/verify",
            headers=self.headers,
            json={"pin": "1234"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("valid"))

    def test_verify_pin_failure(self):
        app.dependency_overrides[get_current_user] = lambda: self.mock_user

        response = self.client.post(
            "/pin/verify",
            headers=self.headers,
            json={"pin": "9999"}
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("Incorrect App PIN", response.json().get("detail", ""))

    def test_withdrawal_pin_enforcement(self):
        app.dependency_overrides[get_current_user] = lambda: self.mock_user
        app.dependency_overrides[require_telecom_kyc_guard] = lambda: self.mock_user

        # 1. Missing PIN payload
        res_missing = self.client.post(
            "/api/v1/mobile-money/withdraw/initiate",
            headers=self.headers,
            json={"amount": 50000, "destination_msisdn": "+256701234567"}
        )
        self.assertEqual(res_missing.status_code, 422)

        # 2. Incorrect PIN
        res_wrong = self.client.post(
            "/api/v1/mobile-money/withdraw/initiate",
            headers=self.headers,
            json={"amount": 50000, "destination_msisdn": "+256701234567", "app_pin": "0000"}
        )
        self.assertEqual(res_wrong.status_code, 401)
        self.assertIn("Incorrect App PIN", res_wrong.json().get("detail", ""))

        # 3. Correct PIN
        res_ok = self.client.post(
            "/api/v1/mobile-money/withdraw/initiate",
            headers=self.headers,
            json={"amount": 50000, "destination_msisdn": "+256701234567", "app_pin": "1234"}
        )
        self.assertEqual(res_ok.status_code, 200)
        self.assertEqual(res_ok.json().get("status"), "success")

    def tearDown(self):
        app.dependency_overrides.clear()

if __name__ == "__main__":
    unittest.main()
