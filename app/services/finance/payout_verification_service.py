import logging
import httpx
from dataclasses import dataclass
from typing import Optional

from app.api.routes.kyc.nin.prembly.utils import get_prembly_headers, PREMBLY_BASE_URL
from app.services.mobile_money.kyc.telecom_tripwire_service import TelecomKycTripwireService

logger = logging.getLogger(__name__)

from app.services.finance.schemas.verification_result import (
    VerificationResult,
    MTN_PROVIDERS,
    AIRTEL_PROVIDERS,
    BANK_PROVIDER_CODES,
    VERIFICATION_TYPE_MTN,
    VERIFICATION_TYPE_AIRTEL,
    VERIFICATION_TYPE_PREMBLY,
    VERIFICATION_TYPE_MANUAL,
)


class PayoutAccountVerificationService:
    """
    Central account verification service.

    Routes each payout destination or payment method to the correct
    external authority:
      - MTN Mobile Money   → TelecomKycTripwireService (MTN path)
      - Airtel Money       → TelecomKycTripwireService (Airtel path)
      - Bank Account       → Prembly bank account verification
      - Unknown            → MANUAL fallback (no external call)
    """

    @classmethod
    def resolve_account_type(
        cls,
        provider_name: str,
        account_number: str = "",
        account_type: Optional[str] = None
    ) -> str:
        """
        Infers whether an account is 'MOBILE_MONEY' or 'BANK_ACCOUNT',
        even if the user or mobile client did not provide account_type.
        """
        if account_type:
            clean = account_type.strip().upper()
            if clean in ["BANK_ACCOUNT", "BANK"]:
                return "BANK_ACCOUNT"
            if clean in ["MOBILE_MONEY", "MOBILE MONEY", "MOMO"]:
                return "MOBILE_MONEY"

        prov = (provider_name or "").strip().lower()
        if "mtn" in prov or "airtel" in prov or "momo" in prov:
            return "MOBILE_MONEY"

        # Check bank keywords
        for bank_name in BANK_PROVIDER_CODES:
            if bank_name.lower() in prov or prov in bank_name.lower():
                return "BANK_ACCOUNT"

        # Check account number digit length (Ugandan phone numbers)
        digits = "".join(filter(str.isdigit, account_number or ""))
        if (len(digits) == 10 and digits.startswith("07")) or (len(digits) == 12 and digits.startswith("2567")):
            return "MOBILE_MONEY"

        return "MOBILE_MONEY"

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    @classmethod
    async def verify(
        cls,
        provider_name: str,
        account_type: Optional[str] = None,
        account_number: str = "",
        bank_code: Optional[str] = None,
    ) -> VerificationResult:
        """
        Determine the verification path from provider_name + account_type
        and dispatch to the correct verifier. Handles case-insensitivity,
        shorthands ('mtn', 'airtel', 'aitel'), and phone prefix matching.
        """
        prov_clean = (provider_name or "").strip().lower()
        type_clean = (account_type or "").strip().upper() if account_type else ""
        if type_clean in ["STRING", ""]:
            type_clean = None

        # Clean dummy bank_code if Swagger placeholder
        clean_bank_code = bank_code if bank_code and bank_code.strip().lower() not in ["string", ""] else None

        # Digits for Uganda phone prefix analysis
        digits = "".join(filter(str.isdigit, account_number or ""))

        is_mtn = (
            "mtn" in prov_clean
            or "momo" in prov_clean
            or any(p.lower() == prov_clean for p in MTN_PROVIDERS)
            or digits.startswith(("077", "078", "076", "25677", "25678", "25676"))
        )

        is_airtel = (
            "airtel" in prov_clean
            or "aitel" in prov_clean
            or "artel" in prov_clean
            or any(p.lower() == prov_clean for p in AIRTEL_PROVIDERS)
            or digits.startswith(("070", "075", "074", "25670", "25675", "25674"))
        )

        # 1. Check for MTN (handles 'mtn', 'mtn mobile money', 'momo', 077/078/076)
        if is_mtn and type_clean != "BANK_ACCOUNT":
            return await cls._verify_mtn_subscriber(account_number)

        # 2. Check for Airtel (handles 'airtel', 'aitel', 'artel', 070/075/074)
        if is_airtel and type_clean != "BANK_ACCOUNT":
            return await cls._verify_airtel_subscriber(account_number)

        # 3. Check for Bank Account (Prembly)
        is_bank_type = type_clean in ["BANK_ACCOUNT", "BANK"]
        matched_bank_code = clean_bank_code or BANK_PROVIDER_CODES.get(provider_name)
        if not matched_bank_code:
            for k, code in BANK_PROVIDER_CODES.items():
                if k.lower() in prov_clean or prov_clean in k.lower():
                    matched_bank_code = code
                    break

        if is_bank_type or matched_bank_code:
            if matched_bank_code:
                return await cls._verify_bank_account_prembly(matched_bank_code, account_number)

        # Fallback: unknown provider or account type
        logger.warning(
            f"[PAYOUT_VERIFICATION] No verifier for provider='{provider_name}' "
            f"account_type='{account_type}'. Falling back to MANUAL."
        )
        return VerificationResult(
            is_verified=False,
            verified_name=None,
            verification_type=VERIFICATION_TYPE_MANUAL,
            raw_response=None,
        )

    # ------------------------------------------------------------------
    # MTN Subscriber Name Lookup
    # ------------------------------------------------------------------
    @classmethod
    async def _verify_mtn_subscriber(cls, phone_number: str) -> VerificationResult:
        logger.info(f"[PAYOUT_VERIFICATION] MTN lookup for {phone_number}")
        try:
            result = await TelecomKycTripwireService.check_sim_age_and_swap_status(
                phone_number=phone_number
            )
            subscriber_name = result.get("carrier_subscriber_name")
            if subscriber_name and subscriber_name != "Verified Subscriber":
                return VerificationResult(
                    is_verified=True,
                    verified_name=subscriber_name,
                    verification_type=VERIFICATION_TYPE_MTN,
                    raw_response=result,
                )

            # Fallback to live MTNKycService
            try:
                from app.api.routes.kyc.phone.mtn.kyc_service import MTNKycService
                mtn_kyc = MTNKycService()
                user_info = await mtn_kyc.get_basic_user_info(phone_number)
                if user_info:
                    given = user_info.get("given_name") or user_info.get("first_name", "")
                    family = user_info.get("family_name") or user_info.get("last_name", "")
                    full = f"{given} {family}".strip() or user_info.get("name")
                    if full:
                        return VerificationResult(
                            is_verified=True,
                            verified_name=full,
                            verification_type=VERIFICATION_TYPE_MTN,
                            raw_response=user_info,
                        )
            except Exception as e:
                logger.warning(f"[PAYOUT_VERIFICATION] Live MTN API warning: {e}")

            return VerificationResult(
                is_verified=True,
                verified_name="MTN Mobile Money User",
                verification_type=VERIFICATION_TYPE_MTN,
                raw_response=result,
            )
        except Exception as e:
            logger.error(f"[PAYOUT_VERIFICATION] MTN lookup error: {e}")
            return VerificationResult(
                is_verified=False,
                verified_name=None,
                verification_type=VERIFICATION_TYPE_MTN,
                raw_response={"error": str(e)},
            )

    # ------------------------------------------------------------------
    # Airtel Subscriber Name Lookup
    # ------------------------------------------------------------------
    @classmethod
    async def _verify_airtel_subscriber(cls, phone_number: str) -> VerificationResult:
        logger.info(f"[PAYOUT_VERIFICATION] Airtel lookup for {phone_number}")
        try:
            result = await TelecomKycTripwireService.check_sim_age_and_swap_status(
                phone_number=phone_number
            )
            subscriber_name = result.get("carrier_subscriber_name")
            if subscriber_name and subscriber_name != "Verified Subscriber":
                return VerificationResult(
                    is_verified=True,
                    verified_name=subscriber_name,
                    verification_type=VERIFICATION_TYPE_AIRTEL,
                    raw_response=result,
                )

            # Fallback to AirtelKycService
            try:
                from app.api.routes.kyc.phone.airtel.kyc_service import AirtelKycService
                airtel_kyc = AirtelKycService()
                user_info = await airtel_kyc.get_basic_user_info(phone_number)
                if user_info:
                    given = user_info.get("first_name", "")
                    family = user_info.get("last_name", "")
                    full = f"{given} {family}".strip()
                    if full:
                        return VerificationResult(
                            is_verified=True,
                            verified_name=full,
                            verification_type=VERIFICATION_TYPE_AIRTEL,
                            raw_response=user_info,
                        )
            except Exception as e:
                logger.warning(f"[PAYOUT_VERIFICATION] Airtel KYC service warning: {e}")

            return VerificationResult(
                is_verified=True,
                verified_name="Airtel Money User",
                verification_type=VERIFICATION_TYPE_AIRTEL,
                raw_response=result,
            )
        except Exception as e:
            logger.error(f"[PAYOUT_VERIFICATION] Airtel lookup error: {e}")
            return VerificationResult(
                is_verified=False,
                verified_name=None,
                verification_type=VERIFICATION_TYPE_AIRTEL,
                raw_response={"error": str(e)},
            )

    # ------------------------------------------------------------------
    # Prembly Bank Account Verification
    # ------------------------------------------------------------------
    @classmethod
    async def _verify_bank_account_prembly(
        cls, bank_code: str, account_number: str
    ) -> VerificationResult:
        logger.info(f"[PAYOUT_VERIFICATION] Prembly bank lookup: bank={bank_code} account={account_number}")
        endpoint_url = f"{PREMBLY_BASE_URL}/verification/bank_account/basic"
        payload = {"bank": bank_code, "account_number": account_number}

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(endpoint_url, headers=get_prembly_headers(), json=payload)
                data = response.json()

                if response.status_code == 200 and data.get("status") is True:
                    account_name = (data.get("data") or {}).get("account_name")
                    return VerificationResult(
                        is_verified=bool(account_name),
                        verified_name=account_name,
                        verification_type=VERIFICATION_TYPE_PREMBLY,
                        raw_response=data,
                    )
                else:
                    logger.warning(f"[PAYOUT_VERIFICATION] Prembly returned non-success: {data}")
                    return VerificationResult(
                        is_verified=False,
                        verified_name=None,
                        verification_type=VERIFICATION_TYPE_PREMBLY,
                        raw_response=data,
                    )
        except httpx.RequestError as e:
            logger.error(f"[PAYOUT_VERIFICATION] Prembly connection error: {e}")
            # Graceful fallback — do not crash the endpoint
            return VerificationResult(
                is_verified=False,
                verified_name=None,
                verification_type=VERIFICATION_TYPE_MANUAL,
                raw_response={"error": str(e)},
            )
        except Exception as e:
            logger.error(f"[PAYOUT_VERIFICATION] Prembly unexpected error: {e}")
            return VerificationResult(
                is_verified=False,
                verified_name=None,
                verification_type=VERIFICATION_TYPE_MANUAL,
                raw_response={"error": str(e)},
            )

    # ------------------------------------------------------------------
    # Fuzzy Name Similarity Helper
    # ------------------------------------------------------------------
    @staticmethod
    def is_name_similar(name_a: str, name_b: str, threshold: float = 75.0) -> bool:
        """
        Token-aware fuzzy string comparison helper.
        Compares two full names taking into account word order variations.
        """
        if not name_a or not name_b:
            return False

        import difflib
        clean_a = " ".join(sorted(name_a.lower().split()))
        clean_b = " ".join(sorted(name_b.lower().split()))

        ratio = difflib.SequenceMatcher(None, clean_a, clean_b).ratio() * 100.0
        return ratio >= threshold

