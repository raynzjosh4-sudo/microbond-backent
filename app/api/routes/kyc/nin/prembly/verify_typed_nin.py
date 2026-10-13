import httpx
import re
import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session
from app.core.database import get_session
from app.models.user.user import User
from app.api.dependencies import get_current_user
from .schemas import NINSubmissionRequest, NINVerificationResponse
from .utils import get_prembly_headers, PREMBLY_SECRET_KEY, PREMBLY_BASE_URL

logger = logging.getLogger(__name__)

router = APIRouter()

from app.core.rate_limit import RateLimiter

@router.post("/verify", response_model=NINVerificationResponse, dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def verify_ugandan_nin_prembly(
    payload: NINSubmissionRequest, 
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user)
):
    """
    Verifies text-based NIN against the government database.
    """
    cleaned_nin = payload.nin.strip().upper()
    if not re.match(r"^[A-Z0-9]{14}$", cleaned_nin):
        raise HTTPException(status_code=400, detail="Invalid NIN format.")
    
    if not PREMBLY_SECRET_KEY:
        logger.info(f"Mocking Prembly NIN Verification for {cleaned_nin}")
        prembly_response = {
            "message": "NIN verification successful (MOCK)",
            "status": "verified",
            "user_data": {
                "first_name": payload.first_name,
                "last_name": payload.last_name,
                "dob": payload.dob,
                "verification_reference": f"mock_ref_{cleaned_nin}"
            }
        }
    else:
        endpoint_url = f"{PREMBLY_BASE_URL}/verification/ug/nationalid/verification" 
        
        request_payload = {
            "national_id": cleaned_nin,
            "surname": payload.last_name,
            "dob": payload.dob,
            "document_id": payload.document_id
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(endpoint_url, headers=get_prembly_headers(), json=request_payload)
                response_data = response.json()
                
                if response.status_code == 200 and response_data.get("status") == True:
                    prembly_response = {
                        "message": "NIN verification successful",
                        "status": "verified",
                        "user_data": response_data.get("data")
                    }
                else:
                    error_msg = response_data.get('message', response_data.get('detail', 'Invalid request data')) if isinstance(response_data, dict) else 'Invalid Details'
                    raise HTTPException(status_code=400, detail=f"Verification failed: {error_msg}")
                    
            except httpx.RequestError as e:
                logger.error(f"Prembly API connection error: {str(e)}")
                raise HTTPException(status_code=500, detail="Failed to connect to verification service.")
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Prembly verification exception: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
                
    user.kyc_status = "VERIFIED_ACTIVE" if prembly_response.get("status") == "verified" else "FAILED_VERIFICATION"
    user.is_dependent_account = payload.is_dependent
    
    from app.models.user.kyc import KycProfile
    from sqlmodel import select
    
    kyc_profile = session.exec(select(KycProfile).where(KycProfile.user_id == user.id)).first()
    if not kyc_profile:
        kyc_profile = KycProfile(user_id=user.id)
    
    if user.kyc_status == "VERIFIED_ACTIVE":
        # Extract the verified values from the response if available, otherwise fallback to payload
        verified_first = prembly_response['user_data'].get('first_name') or payload.first_name
        verified_last = prembly_response['user_data'].get('last_name') or payload.last_name
        
        kyc_profile.first_name = verified_first
        kyc_profile.last_name = verified_last
        user.full_name = f"{verified_first} {verified_last}"
        kyc_profile.nin = cleaned_nin
        kyc_profile.dob = payload.dob
        kyc_profile.document_id = payload.document_id
        
        # New fields from Prembly
        kyc_profile.middle_name = prembly_response['user_data'].get('middle_name')
        kyc_profile.gender = prembly_response['user_data'].get('gender')
        kyc_profile.photo_base64 = prembly_response['user_data'].get('image')
        
        # Optionally, save the profile picture to the main User table so the UI can easily access it
        if kyc_profile.photo_base64 and not user.profile_picture_url:
            user.profile_picture_url = kyc_profile.photo_base64
            
        kyc_profile.overall_status = "VERIFIED_ACTIVE"
        
        user.kyc_tier = 2
    
    session.add(user)
    session.add(kyc_profile)
    session.commit()
    session.refresh(user)

    return {
        "status": "success",
        "message": prembly_response["message"],
        "data": {
            "nin": cleaned_nin,
            "kyc_status": user.kyc_status,
            "is_dependent": payload.is_dependent,
            "verified_name": user.full_name
        }
    }
