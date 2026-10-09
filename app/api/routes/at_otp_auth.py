import random
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks

from sqlmodel import Session, select

from sqlalchemy.exc import SQLAlchemyError

from pydantic import BaseModel



from app.models.auth.otp import OTPRecord, OTPRequest, OTPVerify

from app.models.user.user import User

from app.communications.sms_service import send_real_otp_sms, sanitize_uganda_phone
from app.core.database import get_session, engine

from app.services.mobile_money.kyc.mtn_kyc import MTNKycService



router = APIRouter(prefix="/api/v1/auth/at-otp", tags=["Authentication (Africa's Talking)"])



class OTPRequestResponse(BaseModel):

    status: str

    message: str

    expires_in_seconds: int



class OTPVerifyResponse(BaseModel):

    status: str

    user_id: uuid.UUID | None

    phone_number: str

    is_new_user: bool

    is_profile_complete: bool



def generate_6digit_code() -> str:

    return str(random.randint(100000, 999999))



async def fetch_and_save_kyc(phone_number: str, user_id: uuid.UUID):

    # Route to Airtel or MTN based on prefix

    clean_phone = phone_number.replace("+", "")

    is_airtel = clean_phone.startswith("25670") or clean_phone.startswith("25675") or clean_phone.startswith("25674")

    

    if is_airtel:

        from app.services.mobile_money.kyc.airtel_kyc import AirtelKycService

        kyc_service = AirtelKycService()

    else:

        from app.services.mobile_money.kyc.mtn_kyc import MTNKycService

        kyc_service = MTNKycService()



    user_info = await kyc_service.get_basic_user_info(phone_number)

    

    if user_info:

        # Airtel's response format might differ from MTN, so we safely extract names

        # Airtel returns first_name, last_name usually, while MTN returns given_name, family_name

        given_name = user_info.get("given_name") or user_info.get("first_name", "")

        family_name = user_info.get("family_name") or user_info.get("last_name", "")

        

        # If the API returned a full string "name" instead, we can split it

        if not given_name and user_info.get("name"):

            parts = user_info.get("name", "").split(" ")

            given_name = parts[0]

            family_name = " ".join(parts[1:])



        full_name = f"{given_name} {family_name}".strip()

        

        if full_name:

            with Session(engine) as session:

                user = session.get(User, user_id)

                if user and not user.full_name:

                    user.full_name = full_name

                    # New users default to Tier 1 since their phone name is verified

                    user.kyc_tier = 1 

                    session.add(user)

                    session.commit()



@router.post(

    "/request-otp", 

    summary="Login / Register: Request OTP", 

    description="Generates a 6-digit OTP and sends it via Africa's Talking SMS. Invalidates any previous unverified OTPs. Max 3 free requests per 24 hours.",

    status_code=status.HTTP_200_OK,

    response_model=OTPRequestResponse

)

def request_otp(payload: OTPRequest, session: Session = Depends(get_session)):

    # 1. Handle phone validation errors

    try:

        phone = sanitize_uganda_phone(payload.phone_number)

    except Exception as e:

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail=str(e)

        )



    # 2. Rate Limiting: Max 3 OTPs per 24 hours per phone number

    twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)

    recent_otps_stmt = select(OTPRecord).where(

        OTPRecord.phone_number == phone,

        OTPRecord.created_at >= twenty_four_hours_ago

    )

    recent_otps = session.exec(recent_otps_stmt).all()

    

    if len(recent_otps) >= 3:

        raise HTTPException(

            status_code=status.HTTP_429_TOO_MANY_REQUESTS,

            detail="You have reached the maximum limit of 3 free OTP requests per day. Please contact support if you need more."

        )



    # 3. Cooldown check: Prevent requesting if an OTP was sent in the last 1 minute

    if recent_otps:

        last_otp = max(recent_otps, key=lambda r: r.created_at)

        # Ensure we're comparing offset-aware datetimes

        if last_otp.created_at > datetime.now(timezone.utc) - timedelta(minutes=1):

            raise HTTPException(

                status_code=status.HTTP_429_TOO_MANY_REQUESTS,

                detail="Please wait at least 1 minute before requesting another OTP."

            )



    otp_code = generate_6digit_code()

    expiry = datetime.now(timezone.utc) + timedelta(minutes=5)



    try:

        # Invalidate older unverified codes for this phone number

        existing_otps = session.exec(

            select(OTPRecord).where(

                OTPRecord.phone_number == phone, 

                OTPRecord.is_used == False

            )

        ).all()

        for record in existing_otps:

            record.is_used = True

            session.add(record)



        # Save new OTP to database

        new_otp = OTPRecord(

            phone_number=phone,

            code=otp_code,

            expires_at=expiry

        )

        session.add(new_otp)

        session.commit()

    except SQLAlchemyError:

        session.rollback()

        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail="Database error occurred while preparing your OTP."

        )



    # 4. Send SMS via Africa's Talking with failure handling

    try:

        sent = send_real_otp_sms(phone_number=phone, code=otp_code)

    except Exception:

        sent = False



    if not sent:

        raise HTTPException(

            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,

            detail="Failed to send SMS OTP. Please try again later."

        )



    return OTPRequestResponse(

        status="success",

        message=f"OTP sent to {phone}",

        expires_in_seconds=300

    )



@router.post(

    "/verify-otp",

    summary="Login / Register: Verify OTP",

    description="Verifies the provided 6-digit OTP. If the OTP is correct and not expired, the user is authenticated.",

    status_code=status.HTTP_200_OK,

    response_model=OTPVerifyResponse

)

def verify_otp(payload: OTPVerify, background_tasks: BackgroundTasks, session: Session = Depends(get_session)):

    try:

        phone = sanitize_uganda_phone(payload.phone_number)

    except Exception as e:

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail=str(e)

        )



    try:

        # Look up active OTP record

        statement = select(OTPRecord).where(

            OTPRecord.phone_number == phone,

            OTPRecord.code == payload.code,

            OTPRecord.is_used == False,

            OTPRecord.expires_at > datetime.now(timezone.utc)

        )

        otp_record = session.exec(statement).first()



        if not otp_record:

            raise HTTPException(

                status_code=status.HTTP_400_BAD_REQUEST,

                detail="Invalid or expired OTP code."

            )



        # Mark OTP as consumed

        otp_record.is_used = True

        session.add(otp_record)



        # Fetch or register user in PostgreSQL

        user_stmt = select(User).where(User.phone_number == phone)

        user = session.exec(user_stmt).first()

        is_new = False



        if not user:

            user = User(

                phone_number=phone,

                is_phone_verified=True,

                is_profile_complete=False

            )

            session.add(user)

            is_new = True



        session.commit()

        session.refresh(user)



        if is_new or not user.full_name:

            # Trigger background task to fetch Name from Telecom Provider

            background_tasks.add_task(fetch_and_save_kyc, user.phone_number, user.id)



        return OTPVerifyResponse(

            status="success",

            user_id=user.id,

            phone_number=user.phone_number,

            is_new_user=is_new,

            is_profile_complete=user.is_profile_complete

        )

    except HTTPException:

        # Re-raise HTTP exceptions so they aren't caught by the general DB exception handler

        raise

    except SQLAlchemyError:

        session.rollback()

        raise HTTPException(

            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,

            detail="Database error occurred during verification."

        )



@router.post("/delivery-report", status_code=status.HTTP_200_OK)

async def sms_delivery_report(request: Request):

    try:

        # Africa's Talking sends delivery reports as Form Data

        form_data = await request.form()

        

        print("\n" + "="*40)

        print("🔔 AFRICA'S TALKING DELIVERY REPORT 🔔")

        print("="*40)

        for key, value in form_data.items():

            print(f"{key}: {value}")

        print("="*40 + "\n")

        

        return {"status": "success"}

    except Exception:

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail="Invalid form data."

        )



class ForceKYCRequest(BaseModel):

    phone_number: str



@router.post("/force-kyc-refresh", summary="Manually trigger KYC fetch (Test Endpoint)")

async def force_kyc_refresh(payload: ForceKYCRequest, session: Session = Depends(get_session)):

    """

    Test endpoint to manually force a KYC fetch for an existing user

    without having to request and verify a new OTP.

    """

    try:

        phone = sanitize_uganda_phone(payload.phone_number)

    except Exception as e:

        raise HTTPException(status_code=400, detail=str(e))

        

    user = session.exec(select(User).where(User.phone_number == phone)).first()

    if not user:

        raise HTTPException(status_code=404, detail="User not found in the database. Make sure the phone is registered.")

    

    clean_phone = phone.replace("+", "")

    is_airtel = clean_phone.startswith("25670") or clean_phone.startswith("25675") or clean_phone.startswith("25674")

    

    if is_airtel:

        from app.services.mobile_money.kyc.airtel_kyc import AirtelKycService

        kyc_service = AirtelKycService()

        provider = "Airtel"

    else:

        from app.services.mobile_money.kyc.mtn_kyc import MTNKycService

        kyc_service = MTNKycService()

        provider = "MTN"

    

    user_info = await kyc_service.get_basic_user_info(phone)

    

    if user_info:

        given_name = user_info.get("given_name") or user_info.get("first_name", "")

        family_name = user_info.get("family_name") or user_info.get("last_name", "")

        

        if not given_name and user_info.get("name"):

            parts = user_info.get("name", "").split(" ")

            given_name = parts[0]

            family_name = " ".join(parts[1:])



        full_name = f"{given_name} {family_name}".strip()

        

        if full_name:

            user.full_name = full_name

            user.kyc_tier = 1

            session.add(user)

            session.commit()

            session.refresh(user)

            return {

                "status": "success", 

                "message": f"KYC successfully fetched and saved from {provider}!", 

                "full_name": full_name,

                "raw_data": user_info

            }

        else:

            return {"status": "failed", "message": f"{provider} API succeeded but returned empty names.", "raw_data": user_info}

    else:

        raise HTTPException(status_code=500, detail=f"Failed to fetch KYC from {provider}. Check the server logs.")

