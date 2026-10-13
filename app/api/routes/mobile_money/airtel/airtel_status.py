from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
def airtel_status():
    return {"status": "ok", "provider": "Airtel"}
