from fastapi import APIRouter
from .sync_contacts import router as sync_router, sync_contacts
from .schemas import ContactSyncRequest, MatchedContact

router = APIRouter(prefix="/contacts", tags=["Contacts Discovery"])
router.include_router(sync_router)

__all__ = [
    "router",
    "sync_contacts",
    "ContactSyncRequest",
    "MatchedContact",
]
