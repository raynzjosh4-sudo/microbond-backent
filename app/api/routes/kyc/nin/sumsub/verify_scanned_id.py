import httpx
import json
import logging
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from app.models.user.user import User
from app.api.dependencies import get_current_user
from .utils import generate_sumsub_signature, SUMSUB_APP_TOKEN, SUMSUB_SECRET_KEY, SUMSUB_BASE_URL

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/verify-document")
async def verify_id_document_sumsub(
    id_image: UploadFile = File(...), 
    doc_country: str = Form("UG"),
    user: User = Depends(get_current_user)
):
    """
    Accepts an image upload of the ID card and sends it to Sumsub for verification.
    """
    if not SUMSUB_APP_TOKEN or not SUMSUB_SECRET_KEY:
        logger.info(f"Mocking Sumsub Document Scan Verification for {user.id}")
        return {
            "message": "Document scanned and verification initiated successfully (MOCK)",
            "applicant_id": f"mock_{user.id}"
        }
        
    async with httpx.AsyncClient() as client:
        # Step 1: Create Applicant (if one doesn't exist, we just create one for this doc scan)
        create_applicant_path = f"/resources/applicants?levelName=basic-kyc-level"
        applicant_payload = {
            "externalUserId": str(user.id),
            "info": {"country": doc_country}
        }
        applicant_body = json.dumps(applicant_payload).encode('utf-8')
        headers = generate_sumsub_signature("POST", create_applicant_path, applicant_body)
        
        applicant_response = await client.post(SUMSUB_BASE_URL + create_applicant_path, headers=headers, content=applicant_body)
        if applicant_response.status_code not in (200, 201):
            raise HTTPException(status_code=400, detail=f"Failed to create applicant: {applicant_response.text}")
            
        applicant_id = applicant_response.json().get("id")

        # Step 2: Upload the document image
        image_bytes = await id_image.read()
        
        # Sumsub requires multipart/form-data for document images
        add_doc_path = f"/resources/applicants/{applicant_id}/info/idDoc"
        
        # We need a different signature for multipart form data, but the path is what matters. 
        # Actually for multipart, sumsub expects empty body in signature generation
        doc_headers = generate_sumsub_signature("POST", add_doc_path, b"")
        
        # In httpx, sending a file means it automatically sets the multipart boundary
        # So we need to remove Content-Type from our pre-generated signature headers 
        # so httpx can inject the correct multipart/form-data boundary.
        if "Content-Type" in doc_headers:
            del doc_headers["Content-Type"]
            
        files = {
            "content": (id_image.filename, image_bytes, id_image.content_type)
        }
        data = {
            "metadata": json.dumps({"idDocType": "ID_CARD", "country": doc_country})
        }
        
        doc_response = await client.post(SUMSUB_BASE_URL + add_doc_path, headers=doc_headers, data=data, files=files)
        if doc_response.status_code not in (200, 201):
            raise HTTPException(status_code=400, detail=f"Failed to upload document: {doc_response.text}")

        # Step 3: Trigger the verification process
        request_check_path = f"/resources/applicants/{applicant_id}/status/pending"
        check_headers = generate_sumsub_signature("POST", request_check_path, b"")
        check_response = await client.post(SUMSUB_BASE_URL + request_check_path, headers=check_headers)
        if check_response.status_code not in (200, 201):
             raise HTTPException(status_code=400, detail=f"Failed to trigger check: {check_response.text}")

        return {
            "message": "Document uploaded and verification initiated successfully",
            "applicant_id": applicant_id,
            "status": "pending_verification"
        }
