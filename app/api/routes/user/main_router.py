from fastapi import APIRouter
from .general.profile_status import router as profile_router

router = APIRouter()

router.include_router(profile_router)
