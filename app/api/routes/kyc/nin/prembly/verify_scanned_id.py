import httpx
import logging
import base64
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from app.models.user.user import User
from app.api.dependencies import get_current_user
from .utils import get_prembly_headers, PREMBLY_SECRET_KEY, PREMBLY_BASE_URL

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/verify-document")
async def verify_id_document(
    id_image: UploadFile = File(...), 
    doc_country: str = Form("UG"),
    user: User = Depends(get_current_user)
):
    """
    Accepts an image upload of the ID card, converts it to base64, 
    and sends it to Prembly for OCR scanning and authenticity checks.
    """
    if not PREMBLY_SECRET_KEY:
        return {
            "message": "Document scanned and verified successfully (MOCK)",
            "status": "verified",
            "extracted_data": {
                "document_number": f"MOCK-NIN-{user.id}"
            }
        }
        
    image_bytes = await id_image.read()
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    
    endpoint_url = f"{PREMBLY_BASE_URL}/identitypass/verification/document"
    
    payload = {
        "doc_type": "ID",           # ID = Government issued Identity Card
        "doc_country": doc_country, # "UG" for Uganda
        "doc_image": base64_image   # The encoded image string
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(endpoint_url, headers=get_prembly_headers(), json=payload, timeout=30.0)
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get("status") == True:
                return {
                    "message": "Document scanned and verified successfully",
                    "status": "verified",
                    "extracted_data": response_data.get("data")
                }
            else:
                error_msg = response_data.get('message', 'Document Scan Failed') if isinstance(response_data, dict) else 'Document Scan Failed'
                raise HTTPException(status_code=400, detail=f"Verification failed: {error_msg}")
        except httpx.RequestError as e:
            logger.error(f"Prembly API connection error during doc scan: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to connect to document verification service.")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Prembly document verification exception: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
