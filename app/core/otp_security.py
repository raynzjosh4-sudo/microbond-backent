import hashlib
import hmac
import secrets

from app.core.config import settings

OTP_TTL_SECONDS = 5 * 60


def generate_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(phone: str, otp: str) -> str:
    pepper = settings.OTP_PEPPER
    if not pepper:
        raise RuntimeError("OTP_PEPPER must be configured.")

    message = f"{phone}:{otp}".encode("utf-8")
    return hmac.new(pepper.encode("utf-8"), message, hashlib.sha256).hexdigest()
