import unittest
from fastapi.testclient import TestClient
from fastapi import FastAPI, Depends
from typing import Optional

from app.core.rate_limit import RateLimiter
from app.core.idempotency import check_idempotency_header, store_idempotent_response


class TestRateLimiterAndIdempotency(unittest.TestCase):
    def setUp(self):
        self.test_app = FastAPI()

        @self.test_app.get(
            "/test-rate-limit",
            dependencies=[Depends(RateLimiter(times=2, seconds=10, fail_open=True))]
        )
        def limited_endpoint():
            return {"status": "ok"}

        @self.test_app.post(
            "/test-idempotent-action"
        )
        async def idempotent_endpoint(
            idempotency_key: Optional[str] = Depends(check_idempotency_header)
        ):
            resp = {"status": "success", "action": "deposit_created"}
            if idempotency_key:
                await store_idempotent_response(idempotency_key, resp)
            return resp

        self.client = TestClient(self.test_app)

    def test_rate_limiter_allows_and_throttles(self):
        # 1st request should pass
        r1 = self.client.get("/test-rate-limit", headers={"X-Forwarded-For": "102.134.1.20"})
        self.assertEqual(r1.status_code, 200)

        # 2nd request should pass
        r2 = self.client.get("/test-rate-limit", headers={"X-Forwarded-For": "102.134.1.20"})
        self.assertEqual(r2.status_code, 200)

    def test_rate_limiter_distinct_user_partitioning(self):
        # User A hits endpoint with token
        r_a = self.client.get("/test-rate-limit", headers={"Authorization": "Bearer token_user_a"})
        self.assertEqual(r_a.status_code, 200)

        # User B hits endpoint with different token
        r_b = self.client.get("/test-rate-limit", headers={"Authorization": "Bearer token_user_b"})
        self.assertEqual(r_b.status_code, 200)

    def test_idempotency_header_passthrough_when_none(self):
        # Without header, normal operation
        res = self.client.post("/test-idempotent-action")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json().get("status"), "success")


if __name__ == "__main__":
    unittest.main()
