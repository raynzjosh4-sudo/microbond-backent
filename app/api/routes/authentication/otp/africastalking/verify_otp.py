from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlmodel import Session, select
from sqlalchemy.exc import SQLAlchemyError
from app.models.auth.otp import OTPRecord
from app.models.user.user import User
from app.communications.sms_service import sanitize_uganda_phone
from app.core.database import get_session
from app.core.security import create_access_token
from app.api.routes.kyc.phone.fetch_and_save_kyc import fetch_and_save_kyc
from .schemas import OTPVerify, OTPVerifyResponse

router = APIRouter()

@router.post(
    "/verify-otp",
    summary="Login / Register: Verify OTP",
    description="Verifies the provided 6-digit OTP. If the OTP is correct and not expired, the user is authenticated.",
    status_code=status.HTTP_200_OK,
    response_model=OTPVerifyResponse,
)
def verify_otp(
    payload: OTPVerify,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    try:
        phone = sanitize_uganda_phone(payload.phone_number)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    try:
        # Look up active OTP record
        statement = select(OTPRecord).where(
            OTPRecord.phone_number == phone,
            OTPRecord.code == payload.code,
            OTPRecord.is_used == False,
            OTPRecord.expires_at > datetime.now(timezone.utc),
        )
        otp_record = session.exec(statement).first()

        if not otp_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired OTP code.",
            )

        # Mark OTP as consumed
        otp_record.is_used = True
        session.add(otp_record)

        # Fetch or register user in PostgreSQL
        user_stmt = select(User).where(User.phone_number == phone)
        user = session.exec(user_stmt).first()
        is_new = False
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

        if not user:
            from app.utils.avatar_colors import pick_random_avatar_color
            user = User(
                phone_number=phone, 
                is_phone_verified=True, 
                is_profile_complete=False,
                primary_device_id=payload.device_id,
                avatar_color=pick_random_avatar_color()
            )
            session.add(user)
            is_new = True
        else:
            # SIM-Swap / Account Takeover Detection
            if payload.device_id:
                if user.primary_device_id is None:
                    # First time capturing hardware fingerprint
                    user.primary_device_id = payload.device_id
                elif user.primary_device_id != payload.device_id:
                    # The device changed! Hardware mismatch detected (Potential SIM-Swap / Account Takeover).
                    # 1. Lock down financial movements for 48 hours.
                    user.primary_device_id = payload.device_id
                    user.security_cooldown_until = now_ms + (48 * 60 * 60 * 1000)
                    
                    # 2. Invalidate KYC state: require biometric/NIN re-verification
                    user.kyc_status = "RE_VERIFICATION_REQUIRED"
                    user.kyc_tier = 0

                    # 3. Fire Out-of-Band Email Alert if verified backup email exists
                    from app.models.user.security_email import UserSecurityEmail
                    sec_email = session.exec(
                        select(UserSecurityEmail).where(
                            UserSecurityEmail.user_id == user.id,
                            UserSecurityEmail.is_verified == True
                        )
                    ).first()

                    if sec_email:
                        from app.services.communication.email_service import EmailNotificationService
                        background_tasks.add_task(
                            EmailNotificationService.send_security_alert_new_device,
                            sec_email.email,
                            user.phone_number,
                            payload.device_id,
                            48
                        )
            session.add(user)

        session.commit()
        session.refresh(user)

        if is_new or not user.full_name:
            # Trigger background task to fetch Name from Telecom Provider
            background_tasks.add_task(fetch_and_save_kyc, user.phone_number, user.id)

        # Generate JWT Token
        access_token = create_access_token(
            data={"sub": str(user.id), "phone": user.phone_number}
        )

        return OTPVerifyResponse(
            status="success",
            access_token=access_token,
            user_id=user.id,
            phone_number=user.phone_number,
            is_new_user=is_new,
            is_profile_complete=user.is_profile_complete,
            has_app_pin=bool(user.hashed_pin is not None),
            full_name=user.full_name,
            avatar_url=user.profile_picture_url,
            profile_picture_url=user.profile_picture_url,
            avatar_color=user.avatar_color,
            about_status=user.about_status,
        )
    except HTTPException:
        # Re-raise HTTP exceptions so they aren't caught by the general DB exception handler
        raise
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred during verification.",
        )
