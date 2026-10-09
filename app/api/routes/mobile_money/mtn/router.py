from fastapi import APIRouter

router = APIRouter(prefix="/mtn", tags=["Mobile Money (MTN)"])

@router.get("/status")
def mtn_status():
    return {"status": "ok", "provider": "MTN"}
