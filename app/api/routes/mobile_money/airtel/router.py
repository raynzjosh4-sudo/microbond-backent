from fastapi import APIRouter

router = APIRouter(prefix="/airtel", tags=["Mobile Money (Airtel)"])

@router.get("/status")
def airtel_status():
    return {"status": "ok", "provider": "Airtel"}
