import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from app.models.user.user import User
from app.core.database import get_session, engine
from app.communications.sms_service import sanitize_uganda_phone

router = APIRouter()

async def fetch_and_save_kyc(phone_number: str, user_id: uuid.UUID):
    clean_phone = phone_number.replace("+", "")
    is_airtel = (
        clean_phone.startswith("25670")
        or clean_phone.startswith("25675")
        or clean_phone.startswith("25674")
    )
    if is_airtel:
        from app.services.mobile_money.kyc.airtel_kyc import AirtelKycService
        kyc_service = AirtelKycService()
    else:
        from app.services.mobile_money.kyc.mtn_kyc import MTNKycService
        kyc_service = MTNKycService()

    user_info = await kyc_service.get_basic_user_info(phone_number)

    if user_info:
        given_name = user_info.get("given_name") or user_info.get("first_name", "")
        family_name = user_info.get("family_name") or user_info.get("last_name", "")

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
                    user.kyc_tier = 1
                    session.add(user)
                    session.commit()


class ForceKYCRequest(BaseModel):
    phone_number: str


@router.post("/force-kyc-refresh", summary="Manually trigger KYC fetch (Test Endpoint)")
async def force_kyc_refresh(
    payload: ForceKYCRequest, session: Session = Depends(get_session)
):
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
        raise HTTPException(
            status_code=404,
            detail="User not found in the database. Make sure the phone is registered.",
        )

    clean_phone = phone.replace("+", "")
    is_airtel = (
        clean_phone.startswith("25670")
        or clean_phone.startswith("25675")
        or clean_phone.startswith("25674")
    )

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
                "raw_data": user_info,
            }
        else:
            return {
                "status": "failed",
                "message": f"{provider} API succeeded but returned empty names.",
                "raw_data": user_info,
            }
    else:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch KYC from {provider}. Check the server logs.",
        )
