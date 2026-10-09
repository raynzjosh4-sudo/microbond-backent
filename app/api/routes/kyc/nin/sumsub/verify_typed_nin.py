import httpx
import re
import json
import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session
from app.core.database import get_session
from app.models.user.user import User
from app.api.dependencies import get_current_user
from .schemas.models import NINSubmissionRequest
from .utils import generate_sumsub_signature, SUMSUB_APP_TOKEN, SUMSUB_SECRET_KEY, SUMSUB_BASE_URL

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/verify")
async def verify_ugandan_nin_sumsub(
    payload: NINSubmissionRequest, 
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user)
):
    cleaned_nin = payload.nin.strip().upper()
    if not re.match(r"^[A-Z0-9]{14}$", cleaned_nin):
        raise HTTPException(status_code=400, detail="Invalid NIN format.")
    
    if not SUMSUB_APP_TOKEN or not SUMSUB_SECRET_KEY:
        sumsub_response = {
            "message": "NIN verification initiated successfully (MOCK)",
            "applicant_id": f"mock_{user.id}"
        }
    else:
        async with httpx.AsyncClient() as client:
            create_applicant_path = f"/resources/applicants?levelName=basic-kyc-level"
            applicant_payload = {
                "externalUserId": str(user.id),
                "info": {"firstName": payload.first_name, "lastName": payload.last_name, "dob": payload.dob, "country": "UGA"}
            }
            applicant_body = json.dumps(applicant_payload).encode('utf-8')
            headers = generate_sumsub_signature("POST", create_applicant_path, applicant_body)
            
            applicant_response = await client.post(SUMSUB_BASE_URL + create_applicant_path, headers=headers, content=applicant_body)
            if applicant_response.status_code not in (200, 201):
                raise HTTPException(status_code=400, detail=f"Failed to create applicant: {applicant_response.text}")
                
            applicant_id = applicant_response.json().get("id")

            add_id_path = f"/resources/applicants/{applicant_id}/info/idDoc"
            id_payload = {"idDocType": "ID_CARD", "country": "UGA", "number": cleaned_nin}
            id_body = json.dumps(id_payload).encode('utf-8')
            id_headers = generate_sumsub_signature("POST", add_id_path, id_body)
            
            id_response = await client.post(SUMSUB_BASE_URL + add_id_path, headers=id_headers, content=id_body)
            if id_response.status_code not in (200, 201):
                raise HTTPException(status_code=400, detail=f"Failed to submit NIN: {id_response.text}")

            request_check_path = f"/resources/applicants/{applicant_id}/status/pending"
            check_headers = generate_sumsub_signature("POST", request_check_path, b"")
            check_response = await client.post(SUMSUB_BASE_URL + request_check_path, headers=check_headers)
            if check_response.status_code not in (200, 201):
                 raise HTTPException(status_code=400, detail=f"Failed to trigger check: {check_response.text}")

            sumsub_response = {
                "message": "NIN verification initiated successfully",
                "applicant_id": applicant_id
            }
    
    user.kyc_status = "PENDING_VERIFICATION"
    user.is_dependent_account = payload.is_dependent
    
    session.add(user)
    session.commit()
    session.refresh(user)

    return {
        "status": "success",
        "message": sumsub_response["message"],
        "data": {
            "nin": cleaned_nin,
            "applicant_id": sumsub_response["applicant_id"],
            "kyc_status": user.kyc_status,
            "is_dependent": payload.is_dependent
        }
    }
