from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select
from app.core.database import get_session
from app.models.user.user import User
from app.models.auth.otp import OTPRecord
from app.communications.sms_service import send_real_otp_sms, sanitize_uganda_phone
from app.utils.codes import generate_6digit_code
from app.api.dependencies import get_current_user
from .schemas import RequestChangePhoneOTPRequest, RequestChangePhoneOTPResponse

router = APIRouter()

@router.post("/change-phone/request-otp", response_model=RequestChangePhoneOTPResponse, summary="Request OTP to change phone number", status_code=status.HTTP_200_OK)
def request_change_phone_otp(
    payload: RequestChangePhoneOTPRequest, 
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user)
):
    try:
        new_phone = sanitize_uganda_phone(payload.new_phone_number)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
        
    existing_user_stmt = select(User).where(User.phone_number == new_phone)
    existing_user = session.exec(existing_user_stmt).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New phone number is already registered.")

    twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_otps_stmt = select(OTPRecord).where(
        OTPRecord.phone_number == new_phone,
        OTPRecord.created_at >= twenty_four_hours_ago
    )
    recent_otps = session.exec(recent_otps_stmt).all()
    
    if len(recent_otps) >= 3:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You have reached the maximum limit of 3 free OTP requests per day. Please contact support if you need more."
        )

    if recent_otps:
        last_otp = max(recent_otps, key=lambda r: r.created_at)
        if last_otp.created_at > datetime.now(timezone.utc) - timedelta(minutes=1):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait at least 1 minute before requesting another OTP."
            )

    otp_code = generate_6digit_code()
    expiry = datetime.now(timezone.utc) + timedelta(minutes=5)

    try:
        existing_otps = session.exec(
            select(OTPRecord).where(
                OTPRecord.phone_number == new_phone, 
                OTPRecord.is_used == False
            )
        ).all()
        for record in existing_otps:
            record.is_used = True
            session.add(record)
    
        new_otp = OTPRecord(phone_number=new_phone, code=otp_code, expires_at=expiry)
        session.add(new_otp)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while preparing your OTP."
        )

    try:
        sent = send_real_otp_sms(phone_number=new_phone, code=otp_code)
    except Exception:
        sent = False

    if not sent:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Failed to send SMS OTP. Please try again later.")

    return RequestChangePhoneOTPResponse(
        status="success",
        message=f"OTP sent to {new_phone}",
        expires_in_seconds=300
    )
