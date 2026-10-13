from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
def mtn_status():
    return {"status": "ok", "provider": "MTN"}
