import time
from fastapi import Depends, HTTPException, status
from sqlmodel import Session

from app.core.database import get_session
from app.models.user.user import User
from app.api.dependencies.auth.get_current_user import get_current_user

async def require_telecom_kyc_guard(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
) -> User:
    """
    High-Security Financial Operation Dependency:
    Pre-flight check that queries the telecom carrier (MTN / Airtel) to verify:
    1. The SIM card was NOT swapped within the last 72 hours.
    2. Account is not under an active Security Cooldown.
    3. KYC state is not locked into RE_VERIFICATION_REQUIRED.
    """
    now_ms = int(time.time() * 1000)

    # 1. Check local security cooldown
    if current_user.security_cooldown_until and current_user.security_cooldown_until > now_ms:
        remaining_hours = round((current_user.security_cooldown_until - now_ms) / (3600 * 1000), 1)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Security Cooldown Active: Account is restricted for another {remaining_hours} hours following a device/line change."
        )

    # 2. Check KYC status
    if current_user.kyc_status == "RE_VERIFICATION_REQUIRED":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Telecom Line Identity Mismatch: Mandatory biometric or National ID re-verification is required before proceeding."
        )

    # 3. Live Telecom Carrier SIM Age Query
    from app.services.mobile_money.kyc.telecom_tripwire_service import TelecomKycTripwireService
    carrier_status = await TelecomKycTripwireService.check_sim_age_and_swap_status(
        phone_number=current_user.phone_number,
        current_subscriber_name=current_user.full_name
    )

    if carrier_status.get("is_swapped_recently") or carrier_status.get("hours_since_swap", 999) < 72.0:
        # Tripwire activated!
        current_user.kyc_status = "RE_VERIFICATION_REQUIRED"
        current_user.kyc_tier = 0
        current_user.security_cooldown_until = now_ms + (72 * 3600 * 1000) # 72hr lock
        session.add(current_user)
        session.commit()

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Carrier Tripwire Triggered: Recent SIM-swap activity detected on this line. Account locked for protection."
        )

    return current_user
