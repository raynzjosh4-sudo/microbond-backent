import json
import hmac
import hashlib
import unittest
import uuid
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.core.database import engine
from sqlmodel import Session, select
from app.models.user.user import User
from app.models.group.group import Group
from app.models.group.wallet import GroupWallet
from app.models.group.ledger import LedgerEntry


class TestPaymentGatewayIntegration(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.secret = "test_payment_gateway_secret_key_xyz"

        # Create valid User and Group in the database to satisfy foreign key constraints
        with Session(engine) as session:
            user = User(
                id=uuid.uuid4(),
                phone_number=f"+2567{uuid.uuid4().hex[:8]}",
                full_name="Payment Integration Tester",
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            self.test_user_id = user.id

            group = Group(
                group_id=f"grp_{uuid.uuid4().hex[:12]}",
                name="Payment Integration Test Group",
                group_image_url="https://example.com/icon.png",
                type="SAVINGS_CLUB",
                payment_mode="VOLUNTARY",
                created_by_user_id=self.test_user_id,
            )
            session.add(group)
            session.commit()
            session.refresh(group)
            self.test_group_id = group.group_id

    def test_missing_and_invalid_hmac_rejected(self):
        with patch.object(settings, "PAYMENT_GATEWAY_WEBHOOK_SECRET", self.secret):
            payload = {
                "event_id": str(uuid.uuid4()),
                "event_type": "payment.collection.success",
                "external_reference_id": f"tx_telecom_{uuid.uuid4().hex[:8]}",
                "group_id": self.test_group_id,
                "user_id": str(self.test_user_id),
                "amount": 25000,
                "currency": "UGX",
                "status": "SUCCESS",
            }

            # 1. Missing signature header -> 401
            res_missing = self.client.post(
                "/api/v1/payments/inbound-confirmation",
                json=payload,
            )
            self.assertEqual(res_missing.status_code, 401)
            self.assertIn("Missing payment webhook signature", res_missing.json()["detail"])

            # 2. Tampered / wrong signature -> 401
            res_invalid = self.client.post(
                "/api/v1/payments/inbound-confirmation",
                json=payload,
                headers={"X-Payment-Signature": "wrong_signature_hex"},
            )
            self.assertEqual(res_invalid.status_code, 401)
            self.assertIn("Invalid payment webhook signature", res_invalid.json()["detail"])

    def test_successful_payment_and_idempotency(self):
        with patch.object(settings, "PAYMENT_GATEWAY_WEBHOOK_SECRET", self.secret):
            test_ext_ref = f"telecom_momo_tx_{uuid.uuid4().hex[:10]}"
            deposit_amount = 75000

            payload = {
                "event_id": str(uuid.uuid4()),
                "event_type": "payment.collection.success",
                "external_reference_id": test_ext_ref,
                "group_id": self.test_group_id,
                "user_id": str(self.test_user_id),
                "amount": deposit_amount,
                "currency": "UGX",
                "provider": "MTN_MOMO",
                "source_account": "256772123456",
                "status": "SUCCESS",
            }

            raw_body = json.dumps(payload).encode("utf-8")
            signature = hmac.new(self.secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

            # Mock external push/SMS/WS dispatcher to isolate unit test
            with patch("app.api.routes.payments.inbound_confirmation.inbound_confirmation.broadcast_group_ring_update") as mock_ws, \
                 patch("app.api.routes.payments.inbound_confirmation.inbound_confirmation.enqueue_push_task") as mock_push, \
                 patch("app.api.routes.payments.inbound_confirmation.inbound_confirmation.enqueue_sms_task") as mock_sms:

                # 1. First execution -> Should succeed and credit wallet
                res = self.client.post(
                    "/api/v1/payments/inbound-confirmation",
                    content=raw_body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Payment-Signature": signature,
                    },
                )
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertEqual(data["status"], "SUCCESS")
                self.assertEqual(data["amount_credited"], deposit_amount)
                self.assertIsNotNone(data["ledger_entry_id"])

                # Verify database state: wallet has exactly deposit_amount
                with Session(engine) as session:
                    wallet = session.exec(
                        select(GroupWallet).where(GroupWallet.group_id == self.test_group_id)
                    ).first()
                    self.assertIsNotNone(wallet)
                    self.assertEqual(wallet.pooled_funds, deposit_amount)

                    ledger_entry = session.exec(
                        select(LedgerEntry).where(LedgerEntry.external_reference_id == test_ext_ref)
                    ).first()
                    self.assertIsNotNone(ledger_entry)
                    self.assertEqual(ledger_entry.status, "SETTLED")
                    self.assertEqual(ledger_entry.amount, deposit_amount)

                # 2. Duplicate retry with the EXACT same external_reference_id -> Should return DUPLICATE and NOT double-credit
                res_duplicate = self.client.post(
                    "/api/v1/payments/inbound-confirmation",
                    content=raw_body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Payment-Signature": signature,
                    },
                )
                self.assertEqual(res_duplicate.status_code, 200)
                dup_data = res_duplicate.json()
                self.assertEqual(dup_data["status"], "DUPLICATE")
                self.assertEqual(dup_data["amount_credited"], 0)

                # Verify pooled_funds did NOT double
                with Session(engine) as session:
                    wallet_after = session.exec(
                        select(GroupWallet).where(GroupWallet.group_id == self.test_group_id)
                    ).first()
                    self.assertEqual(wallet_after.pooled_funds, deposit_amount)

    def test_failed_payment_event_handling(self):
        with patch.object(settings, "PAYMENT_GATEWAY_WEBHOOK_SECRET", self.secret):
            payload = {
                "event_id": str(uuid.uuid4()),
                "event_type": "payment.collection.failed",
                "external_reference_id": f"tx_failed_{uuid.uuid4().hex[:8]}",
                "group_id": self.test_group_id,
                "user_id": str(self.test_user_id),
                "amount": 50000,
                "currency": "UGX",
                "status": "FAILED",
                "failure_reason": "Insufficient funds on mobile subscriber line",
            }

            raw_body = json.dumps(payload).encode("utf-8")
            signature = hmac.new(self.secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

            res = self.client.post(
                "/api/v1/payments/inbound-confirmation",
                content=raw_body,
                headers={
                    "Content-Type": "application/json",
                    "X-Payment-Signature": f"sha256={signature}",  # Test sha256= prefix support
                },
            )
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["status"], "FAILED")
            self.assertEqual(data["amount_credited"], 0)
            self.assertIn("Insufficient funds", data["message"])
