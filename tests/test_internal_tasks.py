import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings


class TestInternalTasks(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_internal_tasks_auth_enforced_when_key_set(self):
        # Configure a secret key
        with patch.object(settings, "INTERNAL_TASKS_KEY", "test_secret_12345"):
            # 1. Unauthenticated request should be rejected (401)
            res_unauth = self.client.post("/api/v1/internal/tasks/launch-groups")
            self.assertEqual(res_unauth.status_code, 401)

            # 2. Wrong key should be rejected (401)
            res_wrong = self.client.post(
                "/api/v1/internal/tasks/launch-groups",
                headers={"X-Internal-Secret": "wrong_key"}
            )
            self.assertEqual(res_wrong.status_code, 401)

            # 3. Correct key via header should pass
            with patch("app.api.routes.internal.launch_groups.check_and_launch_pending_groups") as mock_launch:
                res_ok = self.client.post(
                    "/api/v1/internal/tasks/launch-groups",
                    headers={"X-Internal-Secret": "test_secret_12345"}
                )
                self.assertEqual(res_ok.status_code, 200)
                self.assertEqual(res_ok.json().get("status"), "success")
                mock_launch.assert_called_once()

            # 4. Correct key via Bearer authorization should pass
            with patch("app.api.routes.internal.process_payouts.process_due_group_payouts") as mock_payouts:
                res_bearer = self.client.post(
                    "/api/v1/internal/tasks/process-payouts",
                    headers={"Authorization": "Bearer test_secret_12345"}
                )
                self.assertEqual(res_bearer.status_code, 200)
                self.assertEqual(res_bearer.json().get("status"), "success")
                mock_payouts.assert_called_once()

    def test_process_late_fees_and_health_ratings(self):
        with patch.object(settings, "INTERNAL_TASKS_KEY", "secret_key"):
            with patch("app.api.routes.internal.process_late_fees.process_daily_late_fees") as mock_late:
                res = self.client.post(
                    "/api/v1/internal/tasks/process-late-fees",
                    headers={"X-Internal-Secret": "secret_key"}
                )
                self.assertEqual(res.status_code, 200)
                mock_late.assert_called_once()

            with patch("app.api.routes.internal.process_health_ratings.process_daily_health_ratings") as mock_health:
                res = self.client.post(
                    "/api/v1/internal/tasks/process-health-ratings",
                    headers={"X-Internal-Secret": "secret_key"}
                )
                self.assertEqual(res.status_code, 200)
                mock_health.assert_called_once()

    def test_send_sms_task(self):
        with patch.object(settings, "INTERNAL_TASKS_KEY", "secret_key"):
            with patch("app.api.routes.internal.send_sms._send_sms") as mock_send_sms:
                mock_send_sms.return_value = {"status": "sent"}
                res = self.client.post(
                    "/api/v1/internal/tasks/send-sms",
                    headers={"X-Internal-Secret": "secret_key"},
                    json={"phone_number": "0770000000", "message": "Test SMS notification"}
                )
                self.assertEqual(res.status_code, 200)
                self.assertEqual(res.json().get("status"), "success")


if __name__ == "__main__":
    unittest.main()
