from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/mobile-money", tags=["Mobile Money"])

@router.get("/status")
def get_mobile_money_status():
    return {"status": "ok", "message": "Mobile Money API is running"}
