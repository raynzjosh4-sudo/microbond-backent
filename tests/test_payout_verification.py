import unittest
from unittest.mock import patch, AsyncMock
from app.services.finance.payout_verification_service import (
    PayoutAccountVerificationService,
    VERIFICATION_TYPE_MTN,
    VERIFICATION_TYPE_AIRTEL,
    VERIFICATION_TYPE_PREMBLY,
    VERIFICATION_TYPE_MANUAL,
)
from app.models.user.userpayoutaccount.schema.payout_destination_schema import (
    CreatePayoutDestinationRequest,
    PayoutDestinationResponse,
)
from app.models.user.userpaymentmethod.schema.payment_method_schema import (
    CreatePaymentMethodRequest,
    PaymentMethodResponse,
)

class TestPayoutAccountVerification(unittest.IsolatedAsyncioTestCase):

    @patch("app.services.mobile_money.kyc.telecom_tripwire_service.TelecomKycTripwireService.check_sim_age_and_swap_status", new_callable=AsyncMock)
    async def test_verify_mtn_success(self, mock_tripwire):
        mock_tripwire.return_value = {
            "carrier_subscriber_name": "JOHN DOE MUKASA",
            "sim_active": True,
        }

        result = await PayoutAccountVerificationService.verify(
            provider_name="MTN Mobile Money",
            account_type="MOBILE_MONEY",
            account_number="+256771234567"
        )

        self.assertTrue(result.is_verified)
        self.assertEqual(result.verified_name, "JOHN DOE MUKASA")
        self.assertEqual(result.verification_type, VERIFICATION_TYPE_MTN)

    @patch("app.services.mobile_money.kyc.telecom_tripwire_service.TelecomKycTripwireService.check_sim_age_and_swap_status", new_callable=AsyncMock)
    async def test_verify_airtel_success(self, mock_tripwire):
        mock_tripwire.return_value = {
            "carrier_subscriber_name": "SARAH NAKATO",
            "sim_active": True,
        }

        result = await PayoutAccountVerificationService.verify(
            provider_name="Airtel Money",
            account_type="MOBILE_MONEY",
            account_number="+256701234567"
        )

        self.assertTrue(result.is_verified)
        self.assertEqual(result.verified_name, "SARAH NAKATO")
        self.assertEqual(result.verification_type, VERIFICATION_TYPE_AIRTEL)

    @patch("httpx.AsyncClient.post", new_callable=AsyncMock)
    async def test_verify_prembly_bank_success(self, mock_post):
        from unittest.mock import MagicMock
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "status": True,
            "data": {
                "account_name": "JOHN MUKASA",
                "account_number": "9030012345678"
            }
        }
        mock_post.return_value = mock_resp


        result = await PayoutAccountVerificationService.verify(
            provider_name="Stanbic Bank Uganda",
            account_type="BANK_ACCOUNT",
            account_number="9030012345678"
        )

        self.assertTrue(result.is_verified)
        self.assertEqual(result.verified_name, "JOHN MUKASA")
        self.assertEqual(result.verification_type, VERIFICATION_TYPE_PREMBLY)

    async def test_verify_unknown_provider_fallback_manual(self):
        result = await PayoutAccountVerificationService.verify(
            provider_name="Unknown Microfinance SACCO",
            account_type="BANK_ACCOUNT",
            account_number="12345678"
        )

        self.assertFalse(result.is_verified)
        self.assertIsNone(result.verified_name)
        self.assertEqual(result.verification_type, VERIFICATION_TYPE_MANUAL)

    def test_fuzzy_name_matching(self):
        # Exact match
        self.assertTrue(PayoutAccountVerificationService.is_name_similar("John Doe Mukasa", "John Doe Mukasa"))
        # Different word order
        self.assertTrue(PayoutAccountVerificationService.is_name_similar("Mukasa John Doe", "John Doe Mukasa"))
        # Case insensitive
        self.assertTrue(PayoutAccountVerificationService.is_name_similar("john doe mukasa", "JOHN DOE MUKASA"))
        # Unrelated names
        self.assertFalse(PayoutAccountVerificationService.is_name_similar("John Doe", "Sarah Nakato"))
        # Empty names
        self.assertFalse(PayoutAccountVerificationService.is_name_similar("", "John Doe"))

    def test_schema_contracts(self):
        # CreatePayoutDestinationRequest does not require account_name
        req = CreatePayoutDestinationRequest(
            provider_name="MTN Mobile Money",
            account_number="+256771234567",
            account_type="MOBILE_MONEY",
            is_default=True
        )
        self.assertEqual(req.account_type, "MOBILE_MONEY")
        self.assertTrue(req.is_default)

        # PayoutDestinationResponse contains verification fields
        resp = PayoutDestinationResponse(
            id="dest-123",
            provider_name="MTN Mobile Money",
            account_number="+256771234567",
            verified_name="JOHN DOE MUKASA",
            is_verified=True,
            is_default=True,
            masked_number="**** 4567",
            verification_type="MTN"
        )
        self.assertEqual(resp.verified_name, "JOHN DOE MUKASA")
        self.assertTrue(resp.is_verified)
        self.assertEqual(resp.verification_type, "MTN")

if __name__ == "__main__":
    unittest.main()
