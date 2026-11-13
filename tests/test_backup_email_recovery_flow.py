from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool
from sqlalchemy.exc import SQLAlchemyError
import uuid

from app.main import app
from app.core.database import get_session
from app.models.user.user import User
from app.models.user.security_email import UserSecurityEmail
from app.models.auth.otp import OTPRecord
from app.core.security import hash_pin, create_access_token
from app.core.config import settings
from app.core.otp_security import hash_otp


class TestBackupEmailRecoveryFlow(unittest.TestCase):
    def setUp(self):
        self.otp_pepper_patch = patch.object(settings, "OTP_PEPPER", "test-otp-pepper")
        self.otp_pepper_patch.start()
        self.addCleanup(self.otp_pepper_patch.stop)

        # In-memory SQLite for clean isolated tests
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)
        self.session = Session(self.engine)

        def get_test_session():
            with Session(self.engine) as session:
                yield session

        app.dependency_overrides[get_session] = get_test_session
        self.client = TestClient(app)

        # Seed test user
        self.user_id = uuid.uuid4()
        self.old_phone = "+256701111111"
        self.new_phone = "+256702222222"
        self.test_email = "recovery@example.com"

        self.user = User(
            id=self.user_id,
            phone_number=self.old_phone,
            full_name="Alice Namubiru",
            hashed_pin=hash_pin("1111"),
            is_phone_verified=True,
            is_profile_complete=True,
        )
        self.session.add(self.user)
        self.session.commit()

        # Auth token for normal logged-in user
        self.auth_token = create_access_token(
            data={"sub": str(self.user_id), "phone": self.old_phone}
        )
        self.auth_headers = {"Authorization": f"Bearer {self.auth_token}"}

    def tearDown(self):
        app.dependency_overrides.clear()
        self.session.close()

    @patch("app.api.routes.authentication.otp.africastalking.request_otp.send_real_otp_sms")
    def test_login_otp_is_hashed_and_verifies(self, mock_sms):
        mock_sms.return_value = True

        request_response = self.client.post(
            "/api/v1/auth/at-otp/request-otp",
            json={"phone_number": self.old_phone},
        )
        self.assertEqual(request_response.status_code, 200)
        self.assertIn("••••", request_response.json()["message"])

        otp_record = self.session.exec(
            select(OTPRecord).where(OTPRecord.phone_number == self.old_phone)
        ).first()
        self.assertIsNotNone(otp_record)
        otp_code = mock_sms.call_args.kwargs["code"]
        self.assertNotEqual(otp_record.code_hash, otp_code)
        self.assertEqual(otp_record.code_hash, hash_otp(self.old_phone, otp_code))
        self.assertNotIn(otp_code, request_response.text)

        verify_response = self.client.post(
            "/api/v1/auth/at-otp/verify-otp",
            json={"phone_number": self.old_phone, "code": otp_code},
        )
        self.assertEqual(verify_response.status_code, 200)
        self.assertEqual(verify_response.json()["status"], "success")
        self.session.refresh(otp_record)
        self.assertTrue(otp_record.is_used)

    def test_login_otp_daily_limit_is_configurable(self):
        now = datetime.now(timezone.utc)
        self.session.add(
            OTPRecord(
                phone_number=self.old_phone,
                code_hash="already-requested",
                created_at=now,
                expires_at=now + timedelta(minutes=5),
            )
        )
        self.session.commit()

        with patch.object(settings, "OTP_DAILY_REQUEST_LIMIT", 1):
            response = self.client.post(
                "/api/v1/auth/at-otp/request-otp",
                json={"phone_number": self.old_phone},
            )

        self.assertEqual(response.status_code, 429)
        self.assertIn("maximum limit of 1", response.json()["detail"])

    def test_login_otp_verification_returns_database_error_in_debug_mode(self):
        otp = OTPRecord(
            phone_number=self.old_phone,
            code_hash=hash_otp(self.old_phone, "123456"),
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        )
        self.session.add(otp)
        self.session.commit()

        with (
            patch.object(settings, "DEBUG_ERROR_DETAILS", False),
            patch(
                "app.api.routes.authentication.otp.africastalking.verify_otp.Session.commit",
                side_effect=SQLAlchemyError("test database failure"),
            ),
        ):
            response = self.client.post(
                "/api/v1/auth/at-otp/verify-otp",
                json={"phone_number": self.old_phone, "code": "123456"},
            )

        self.assertEqual(response.status_code, 500)
        self.assertIn("test database failure", response.json()["detail"])

    def test_get_backup_email_empty(self):
        """GET /email/backup returns has_backup_email=False when none configured."""
        res = self.client.get("/email/backup", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertFalse(data["has_backup_email"])
        self.assertIsNone(data["data"])

    def test_get_backup_email_configured(self):
        """GET /email/backup returns email and verification state for the logged-in user."""
        sec_email = UserSecurityEmail(
            user_id=self.user_id,
            email=self.test_email,
            is_verified=True,
        )
        self.session.add(sec_email)
        self.session.commit()

        res = self.client.get("/email/backup", headers=self.auth_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["has_backup_email"])
        self.assertEqual(data["data"]["email"], self.test_email)
        self.assertTrue(data["data"]["is_verified"])

    @patch("app.api.routes.authentication.account_recovery.backup_email.request_code.EmailNotificationService.send_email")
    def test_request_email_recovery_code_unverified_or_nonexistent(self, mock_send_email):
        """Requesting recovery code for an unknown or unverified email returns 404."""
        res = self.client.post(
            "/recovery/email/request-code",
            json={"email": "nonexistent@example.com"}
        )
        self.assertEqual(res.status_code, 404)
        mock_send_email.assert_not_called()

    @patch("app.api.routes.authentication.account_recovery.backup_email.request_code.EmailNotificationService.send_email")
    @patch("app.api.routes.authentication.account_recovery.backup_email.request_phone_otp.send_real_otp_sms")
    def test_full_email_recovery_and_phone_update_flow(self, mock_sms, mock_send_email):
        """Full end-to-end flow: request email code -> verify code -> request phone OTP -> confirm phone -> reset PIN."""
        mock_sms.return_value = True

        # 1. Setup verified backup email
        sec_email = UserSecurityEmail(
            user_id=self.user_id,
            email=self.test_email,
            is_verified=True,
        )
        self.session.add(sec_email)
        self.session.commit()

        # 2. Step 1: Request Recovery Code via email (Unauthenticated)
        res_req = self.client.post(
            "/recovery/email/request-code",
            json={"email": self.test_email}
        )
        self.assertEqual(res_req.status_code, 200)
        self.assertEqual(res_req.json()["status"], "success")
        mock_send_email.assert_called_once()

        # Retrieve generated code from database
        self.session.refresh(sec_email)
        email_code = sec_email.verification_token
        self.assertIsNotNone(email_code)

        # 3. Step 2: Verify Recovery Code (Unauthenticated)
        # 3a. Invalid code fails
        res_bad = self.client.post(
            "/recovery/email/verify-code",
            json={"email": self.test_email, "code": "000000"}
        )
        self.assertEqual(res_bad.status_code, 401)

        # 3b. Correct code succeeds and returns temp_recovery_token
        res_verify = self.client.post(
            "/recovery/email/verify-code",
            json={"email": self.test_email, "code": email_code}
        )
        self.assertEqual(res_verify.status_code, 200)
        temp_recovery_token = res_verify.json()["temp_recovery_token"]
        self.assertIsNotNone(temp_recovery_token)

        recovery_headers = {"Authorization": f"Bearer {temp_recovery_token}"}

        # 4. Step 3: Request SMS OTP for new phone number using recovery token
        res_phone_req = self.client.post(
            "/recovery/email/request-phone-otp",
            headers=recovery_headers,
            json={"new_phone_number": self.new_phone}
        )
        self.assertEqual(res_phone_req.status_code, 200)
        mock_sms.assert_called_once()

        # Retrieve SMS OTP from database
        otp_rec = self.session.exec(
            select(OTPRecord).where(OTPRecord.phone_number == self.new_phone)
        ).first()
        self.assertIsNotNone(otp_rec)
        sms_code = mock_sms.call_args.kwargs["code"]
        self.assertEqual(otp_rec.code_hash, hash_otp(self.new_phone, sms_code))

        # 5. Step 4: Confirm SMS OTP and update phone number
        with patch("app.api.routes.authentication.account_recovery.backup_email.confirm_phone.fetch_and_save_kyc"):
            res_confirm = self.client.post(
                "/recovery/email/confirm-phone",
                headers=recovery_headers,
                json={"new_phone_number": self.new_phone, "code": sms_code}
            )
        self.assertEqual(res_confirm.status_code, 200)
        final_recovery_token = res_confirm.json()["recovery_token"]
        self.assertIsNotNone(final_recovery_token)

        # Verify phone number was updated on the user record in database
        self.session.refresh(self.user)
        self.assertEqual(self.user.phone_number, self.new_phone)

        # 6. Step 5: Set new PIN using the recovery token
        final_headers = {"Authorization": f"Bearer {final_recovery_token}"}
        res_pin = self.client.post(
            "/pin/set",
            headers=final_headers,
            json={"pin": "9876"}
        )
        self.assertEqual(res_pin.status_code, 200)
        data_pin = res_pin.json()
        self.assertEqual(data_pin["status"], "success")
        self.assertIn("access_token", data_pin)

        # Account is fully restored with new phone and new PIN!


if __name__ == "__main__":
    unittest.main()
