import httpx
import re
import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session
from app.core.database import get_session
from app.models.user.user import User
from app.api.dependencies import get_current_user
from .schemas.models import NINSubmissionRequest
from .utils import get_prembly_headers, PREMBLY_SECRET_KEY, PREMBLY_BASE_URL

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/verify")
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
        endpoint_url = f"{PREMBLY_BASE_URL}/identitypass/verification/ug/national_id" 
        
        request_payload = {
            "number": cleaned_nin,
            "first_name": payload.first_name,
            "last_name": payload.last_name,
            "dob": payload.dob
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
                    error_msg = response_data.get('message', 'Invalid Details') if isinstance(response_data, dict) else 'Invalid Details'
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
    
    if user.kyc_status == "VERIFIED_ACTIVE":
        user.full_name = f"{prembly_response['user_data'].get('first_name', payload.first_name)} {prembly_response['user_data'].get('last_name', payload.last_name)}"
        user.kyc_tier = 2
    
    session.add(user)
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
