import uuid
from sqlmodel import Session
from app.models.user.user import User
from app.core.database import engine

async def fetch_and_save_kyc(phone_number: str, user_id: uuid.UUID):
    clean_phone = phone_number.replace("+", "")
    is_airtel = (
        clean_phone.startswith("25670")
        or clean_phone.startswith("25675")
        or clean_phone.startswith("25674")
    )
    if is_airtel:
        from .airtel.kyc_service import AirtelKycService
        kyc_service = AirtelKycService()
    else:
        from .mtn.kyc_service import MTNKycService
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
            from app.models.user.kyc import KycProfile
            from sqlmodel import select
            import time
            
            with Session(engine) as session:
                user = session.get(User, user_id)
                if user and not user.full_name:
                    user.full_name = full_name
                    user.kyc_tier = 1
                    
                    kyc_profile = session.exec(select(KycProfile).where(KycProfile.user_id == user.id)).first()
                    if not kyc_profile:
                        kyc_profile = KycProfile(user_id=user.id)
                    
                    kyc_profile.sim_msisdn = phone_number
                    kyc_profile.sim_telecom_provider = "Airtel" if is_airtel else "MTN"
                    kyc_profile.sim_registered_name = full_name
                    kyc_profile.first_name = given_name
                    kyc_profile.last_name = family_name
                    kyc_profile.sim_verified_at = int(time.time() * 1000)
                    kyc_profile.overall_status = "TIER_1_PHONE_VERIFIED"
                    kyc_profile.current_tier = "TIER_1_PHONE_VERIFIED"
                    
                    session.add(user)
                    session.add(kyc_profile)
                    session.commit()
